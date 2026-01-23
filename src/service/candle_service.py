"""Candle data service for saving candle data to database."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from src.common.data_adapter import DataSource
from src.database import Ticker


class CollectMode(StrEnum):
    """캔들 데이터 수집 모드.

    Attributes:
        INCREMENTAL: DB 최신 이후만 수집 (기본값)
        FULL: 전체 수집
        BACKFILL: DB 가장 오래된 이전만 수집
    """

    INCREMENTAL = "INCREMENTAL"
    FULL = "FULL"
    BACKFILL = "BACKFILL"


def _to_utc(dt: datetime) -> datetime:
    """datetime을 UTC로 변환.

    - naive: UTC로 간주하고 tzinfo 추가
    - aware: UTC로 변환

    Args:
        dt: 변환할 datetime

    Returns:
        UTC timezone이 적용된 datetime
    """
    from datetime import UTC as UTC_TZ

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC_TZ)
    else:
        return dt.astimezone(UTC_TZ)


if TYPE_CHECKING:
    import logging

    import pandas as pd

    from src.adapters.adapter_factory import CandleAdapterFactory
    from src.database.models import CandleMinute1
    from src.database.repositories import CandleDailyRepository, CandleMinute1Repository
    from src.service.candle_query_service import CandleQueryService


class CandleService:
    """캔들 데이터 저장 서비스.

    데이터 출처(source)에 맞는 어댑터를 자동 선택하여
    Raw DataFrame을 정규화하고 DB에 저장합니다.

    주요 기능:
    - 어댑터 자동 선택 (Factory 패턴)
    - API CandleInterval → DB interval 변환
    - interval별 적절한 repository 선택
    - Bulk Insert (Upsert)
    """

    def __init__(
            self,
            minute1_repository: "CandleMinute1Repository",
            daily_repository: "CandleDailyRepository",
            adapter_factory: "CandleAdapterFactory",
            query_service: "CandleQueryService",
    ) -> None:
        """CandleService 초기화.

        Args:
            minute1_repository: 1분봉 캔들 데이터 저장소
            daily_repository: 일봉 캔들 데이터 저장소
            adapter_factory: 어댑터 팩토리
            query_service: 통합 캔들 조회 서비스
        """
        self._minute1_repo = minute1_repository
        self._daily_repo = daily_repository
        self._factory = adapter_factory
        self._query_service = query_service

    def collect_minute1_candles(
            self,
            ticker: Ticker,
            start: datetime | None = None,
            to: datetime | None = None,
            batch_size: int = 1000,
            mode: CollectMode = CollectMode.INCREMENTAL
    ) -> int:
        """1분봉 데이터를 수집하여 DB에 저장.

        market과 ticker_id를 받아 데이터를 조회하여 DB에 저장합니다.

        수집 모드:
        - INCREMENTAL (기본): DB의 최신 데이터 이후만 수집
        - FULL: API가 빈 데이터를 반환할 때까지 전체 수집
        - BACKFILL: DB의 가장 오래된 데이터 이전만 수집 (과거 데이터 채우기)

        Args:
            ticker: 종목
            to: 마지막으로 캔들을 마감한 시각 (해당 시각 이전 데이터 수집, None이면 현재 시각)
            start: 수집 시작 일자 (해당 시각 이전 데이터는 수집하지 않음, None이면 제한 없음)
            batch_size: DB 저장 배치 크기 (기본값: 1000)
            mode: 수집 모드 (기본값: CollectMode.INCREMENTAL)

        Returns:
            저장된 총 캔들 개수

        Raises:
            ValueError: 잘못된 market 또는 batch_size
            Exception: API 호출 또는 DB 저장 실패

        Example:
            >>> from src.service.candle_service import CollectMode
            >>> service = CandleService(minute1_repo, daily_repo, factory)
            >>> # 증분 수집 (DB 최신 이후 데이터만)
            >>> total = service.collect_minute1_candles("KRW-BTC")
            >>> # 전체 데이터 재수집
            >>> total = service.collect_minute1_candles("KRW-BTC",mode=CollectMode.FULL)
            >>> # 과거 데이터 채우기
            >>> total = service.collect_minute1_candles("KRW-BTC",mode=CollectMode.BACKFILL)
            >>> print(f"총 {total}개 캔들 저장 완료")
        """
        import logging
        from typing import cast

        from src.common.candle_client import CandleInterval
        from src.database.models import CandleMinute1

        logger = logging.getLogger(__name__)

        if batch_size <= 0:
            raise ValueError("batch_size는 0보다 커야 합니다")

        # 타임존 변환: aware datetime은 UTC로 변환, naive는 UTC로 간주
        if start is not None:
            start = _to_utc(start)
        if to is not None:
            to = _to_utc(to)

        # 모드별 경계 timestamp 조회
        boundary_timestamp, to_date = self._get_mode_boundary(ticker, mode, to, logger)

        accumulated_candles: list[CandleMinute1] = []
        total_saved = 0

        while True:
            try:
                df = self._query_service.get_candles(
                    ticker=ticker,
                    interval=CandleInterval.MINUTE_1,
                    count=batch_size,
                    end_time=to_date,
                )
            except Exception as e:
                logger.error(f"API 호출 실패: {e}")
                raise

            if df.empty:
                logger.info(f"더 이상 수집할 데이터가 없습니다 (market={ticker.ticker})")
                break

            # INCREMENTAL 모드: DB 최신보다 오래된 데이터 필터링
            df = self._filter_by_boundary(df, mode, boundary_timestamp)  # type: ignore[assignment]
            if df.empty:
                logger.info(f"DB 최신 데이터까지 수집 완료 (market={ticker.ticker})")
                break

            # start 이전 데이터 필터링
            df = self._filter_by_start(df, start)  # type: ignore[assignment]
            if df.empty:
                logger.info(f"시작일자({start})에 도달하여 수집 종료 (market={ticker.ticker})")
                break

            candle_models = self._factory.get_common_adapter().to_candle_models(df, ticker.id, CandleInterval.MINUTE_1)

            if not candle_models:
                logger.warning(f"변환된 캔들 데이터가 없습니다 (market={ticker.ticker})")
                break

            # 타입 캐스팅: UpbitCandleInterval.MINUTE_1이므로 CandleMinute1 반환 보장
            accumulated_candles.extend(cast(list[CandleMinute1], candle_models))

            to_date = df.index[0]

            # API가 요청한 개수보다 적게 반환하면 마지막 페이지
            is_last_page = len(df) < batch_size

            logger.info(
                f"수집: {len(candle_models)}개, "
                f"누적: {len(accumulated_candles)}개, "
                f"다음 기준: {to_date} (market={ticker.ticker})"
            )

            # 배치 저장
            if len(accumulated_candles) >= batch_size:
                try:
                    total_saved += self._flush_candles(accumulated_candles, logger)
                    logger.info(f"총 {total_saved}개 저장됨")
                    accumulated_candles.clear()
                except Exception as e:
                    logger.error(f"DB 저장 실패: {e}")
                    raise

            # 마지막 페이지면 루프 종료
            if is_last_page:
                logger.info(f"마지막 페이지 수집 완료 (market={ticker.ticker})")
                break

        # 최종 남은 데이터 저장
        if accumulated_candles:
            try:
                total_saved += self._flush_candles(accumulated_candles, logger)
                logger.info(f"최종 저장 완료, 총 {total_saved}개 저장됨")
            except Exception as e:
                logger.error(f"최종 DB 저장 실패: {e}")
                raise

        logger.info(f"1분봉 데이터 수집 완료: 총 {total_saved}개 (market={ticker.ticker})")
        return total_saved

    def save_candles(
            self,
            df: "pd.DataFrame",
            source: DataSource,
            ticker_id: int,
            interval: object,
    ) -> None:
        """Raw DataFrame을 정규화하여 DB에 저장.

        Args:
            df: 출처의 원본 DataFrame (컬럼명, 타임존 등이 출처마다 다를 수 있음)
            source: 데이터 출처 (DataSource enum)
            ticker_id: 티커 ID (Ticker 테이블의 PK)
            interval: 출처별 interval 타입
                - Upbit: UpbitCandleInterval
                - Binance: BinanceCandleInterval
                - Hantu: OverseasMinuteInterval | OverseasCandlePeriod

        Raises:
            ValueError: 알 수 없는 source 또는 지원하지 않는 interval인 경우

        Example:
            >>> from src.common.data_adapter import DataSource
            >>> from src.upbit.upbit_api import UpbitCandleInterval
            >>> service = CandleService(minute1_repo, daily_repo, factory)
            >>> df = upbit_api.get_candles(interval=UpbitCandleInterval.MINUTE_1)
            >>> service.save_candles(
            ...     df=df,
            ...     source=DataSource.UPBIT,
            ...     ticker_id=1,  # Ticker.id
            ...     interval=UpbitCandleInterval.MINUTE_1
            ... )
            >>> print("캔들 저장 완료")
        """
        from src.database.models import CandleMinute1

        adapter = self._factory.get_adapter(source)
        candle_models = adapter.to_candle_models(df, ticker_id, interval)

        if not candle_models:
            return

        if isinstance(candle_models[0], CandleMinute1):
            self._minute1_repo.bulk_upsert(candle_models)  # type: ignore[arg-type]
        else:
            raise NotImplementedError(
                "1분봉 외의 캔들 데이터 저장은 지원하지 않습니다. "
                "(CandleHour1, CandleDaily는 MATERIALIZED VIEW입니다.)"
            )

    def _flush_candles(
            self,
            candles: list["CandleMinute1"],
            logger: "logging.Logger",
    ) -> int:
        """누적된 캔들 데이터를 DB에 저장하고 저장된 개수 반환.

        Args:
            candles: 저장할 캔들 모델 리스트
            logger: 로거

        Returns:
            저장된 캔들 개수
        """
        if not candles:
            return 0
        self._minute1_repo.bulk_upsert(candles)
        logger.info(f"DB 저장 완료: {len(candles)}개")
        return len(candles)

    @staticmethod
    def _filter_by_boundary(
            df: "pd.DataFrame",
            mode: CollectMode,
            boundary: datetime | None,
    ) -> "pd.DataFrame":
        """INCREMENTAL 모드의 경계 타임스탬프 필터링.

        Args:
            df: 필터링할 DataFrame
            mode: 수집 모드
            boundary: 경계 타임스탬프 (이 시각 이후 데이터만 유지)

        Returns:
            필터링된 DataFrame
        """
        if mode != CollectMode.INCREMENTAL or boundary is None:
            return df
        return df[df["timestamp"] > _to_utc(boundary)]

    @staticmethod
    def _filter_by_start(
            df: "pd.DataFrame",
            start: datetime | None,
    ) -> "pd.DataFrame":
        """시작 시각 필터링.

        Args:
            df: 필터링할 DataFrame
            start: 시작 시각 (이 시각 이후 데이터만 유지)

        Returns:
            필터링된 DataFrame
        """
        if start is None:
            return df
        return df[df["timestamp"] >= start]

    def _get_mode_boundary(
            self,
            ticker: Ticker,
            mode: CollectMode,
            to: datetime | None,
            logger: "logging.Logger",
    ) -> tuple[datetime | None, datetime | None]:
        """모드별 경계 타임스탬프와 to_date 반환.

        Args:
            ticker: 종목
            mode: 수집 모드
            to: 초기 to_date 값
            logger: 로거

        Returns:
            (boundary_timestamp, to_date) 튜플
            - boundary_timestamp: INCREMENTAL 모드에서 DB 최신 타임스탬프
            - to_date: 수집 시작 기준 시각
        """
        boundary_timestamp: datetime | None = None
        to_date = to

        if mode == CollectMode.INCREMENTAL:
            latest = self._minute1_repo.get_latest_candle(ticker.id)
            boundary_timestamp = latest.utc_time if latest else None
            if boundary_timestamp:
                logger.info(f"Incremental 모드: {boundary_timestamp} 이후 데이터만 수집 (market={ticker.ticker})")
            else:
                logger.info(f"DB에 데이터 없음: 전체 데이터 수집 (market={ticker.ticker})")
        elif mode == CollectMode.BACKFILL:
            oldest = self._minute1_repo.get_oldest_candle(ticker.id)
            if oldest:
                to_date = oldest.utc_time
                logger.info(f"Backfill 모드: {oldest.utc_time} 이전 데이터만 수집 (market={ticker.ticker})")
            else:
                logger.info(f"DB에 데이터 없음: 전체 데이터 수집 (market={ticker.ticker})")
        else:  # FULL
            logger.info(f"Full 모드: 전체 데이터 수집 (market={ticker.ticker})")

        return boundary_timestamp, to_date
