"""Candle data service for saving candle data to database."""

from datetime import datetime
from typing import TYPE_CHECKING

from src.common.data_adapter import DataSource

if TYPE_CHECKING:
    import pandas as pd

    from src.adapters.adapter_factory import CandleAdapterFactory
    from src.database.repositories import CandleDailyRepository, CandleMinute1Repository


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
    ) -> None:
        """CandleService 초기화.

        Args:
            minute1_repository: 1분봉 캔들 데이터 저장소
            daily_repository: 일봉 캔들 데이터 저장소@
            adapter_factory: 어댑터 팩토리
        """
        self._minute1_repo = minute1_repository
        self._daily_repo = daily_repository
        self._factory = adapter_factory

    def save_candles(
            self,
            df: "pd.DataFrame",
            source: DataSource,
            ticker: str,
            interval: object,
    ) -> None:
        """Raw DataFrame을 정규화하여 DB에 저장.

        Args:
            df: 출처의 원본 DataFrame (컬럼명, 타임존 등이 출처마다 다를 수 있음)
            source: 데이터 출처 (DataSource enum)
            ticker: 종목 코드 (예: "KRW-BTC", "BTCUSDT", "005930")
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
            ...     ticker="KRW-BTC",
            ...     interval=UpbitCandleInterval.MINUTE_1
            ... )
            >>> print("캔들 저장 완료")
        """
        from src.database.models import CandleMinute1

        adapter = self._factory.get_adapter(source)
        candle_models = adapter.to_candle_models(df, ticker, interval)

        if not candle_models:
            return

        if isinstance(candle_models[0], CandleMinute1):
            self._minute1_repo.bulk_upsert(candle_models)  # type: ignore[arg-type]
        else:
            self._daily_repo.bulk_upsert(candle_models)  # type: ignore[arg-type]

    def collect_minute1_candles(
            self,
            ticker: str,
            to: datetime | None = None,
            batch_size: int = 1000,
    ) -> int:
        """1분봉 데이터를 수집하여 DB에 저장.

        티커를 받아 데이터가 없을 때까지 계속 조회하여 DB에 저장합니다.
        배치 크기만큼 누적되면 DB에 저장하여 메모리 효율성을 높입니다.

        Args:
            ticker: 종목 코드 (예: "KRW-BTC")
            to: 마지막으로 캔들을 마감한 시각 (해당 시각 이전 데이터 수집, None이면 현재 시각)
            batch_size: DB 저장 배치 크기 (기본값: 1000)

        Returns:
            저장된 총 캔들 개수

        Raises:
            ValueError: 잘못된 ticker 또는 batch_size
            Exception: API 호출 또는 DB 저장 실패

        Example:
            >>> service = CandleService(minute1_repo, daily_repo, factory)
            >>> # 모든 데이터 수집
            >>> total = service.collect_minute1_candles("KRW-BTC")
            >>> # 특정 시점 이전 데이터만 수집
            >>> from datetime import datetime
            >>> total = service.collect_minute1_candles("KRW-BTC", to=datetime(2024, 1, 1))
            >>> print(f"총 {total}개 캔들 저장 완료")
        """
        import logging
        from typing import cast

        from src.common.data_adapter import DataSource
        from src.database.models import CandleMinute1
        from src.upbit.upbit_api import UpbitAPI, UpbitCandleInterval

        logger = logging.getLogger(__name__)

        if batch_size <= 0:
            raise ValueError("batch_size는 0보다 커야 합니다")

        latest = self._minute1_repo.get_latest_candle(ticker)
        if latest:
            logger.info(f"마지막 저장 데이터: {latest.timestamp} (ticker={ticker})")

        accumulated_candles: list[CandleMinute1] = []
        total_saved = 0
        to_date: datetime | None = to
        upbit_api = UpbitAPI()

        while True:
            try:
                df = upbit_api.get_candles(
                    market=ticker,
                    interval=UpbitCandleInterval.MINUTE_1,
                    count=batch_size,
                    to=to_date,
                )
            except Exception as e:
                logger.error(f"API 호출 실패: {e}")
                raise

            if df.empty:
                logger.info(f"더 이상 수집할 데이터가 없습니다 (ticker={ticker})")
                break

            candle_models = self._factory.get_adapter(DataSource.UPBIT).to_candle_models(df, ticker, UpbitCandleInterval.MINUTE_1)

            if not candle_models:
                logger.warning(f"변환된 캔들 데이터가 없습니다 (ticker={ticker})")
                break

            # 타입 캐스팅: UpbitCandleInterval.MINUTE_1이므로 CandleMinute1 반환 보장
            accumulated_candles.extend(cast(list[CandleMinute1], candle_models))

            to_date = df.index[0]

            logger.info(
                f"수집: {len(candle_models)}개, "
                f"누적: {len(accumulated_candles)}개, "
                f"다음 기준: {to_date} (ticker={ticker})"
            )

            # 배치 저장
            if len(accumulated_candles) >= batch_size:
                try:
                    self._minute1_repo.bulk_upsert(accumulated_candles)
                    total_saved += len(accumulated_candles)
                    logger.info(f"DB 저장 완료: {len(accumulated_candles)}개 (총 {total_saved}개)")
                    accumulated_candles.clear()
                except Exception as e:
                    logger.error(f"DB 저장 실패: {e}")
                    raise

        # 최종 남은 데이터 저장
        if accumulated_candles:
            try:
                self._minute1_repo.bulk_upsert(accumulated_candles)
                total_saved += len(accumulated_candles)
                logger.info(f"최종 DB 저장 완료: {len(accumulated_candles)}개 (총 {total_saved}개)")
            except Exception as e:
                logger.error(f"최종 DB 저장 실패: {e}")
                raise

        logger.info(f"1분봉 데이터 수집 완료: 총 {total_saved}개 (ticker={ticker})")
        return total_saved
