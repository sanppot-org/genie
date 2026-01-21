"""Candle data adapter implementations for different sources."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

import pandas as pd
import pytz

from src.common.data_adapter import CandleDataAdapter
from src.database.models import CandleBase, CandleDaily, CandleMinute1

T = TypeVar("T", bound=CandleBase)

if TYPE_CHECKING:
    pass


class UpbitCandleAdapter(CandleDataAdapter):
    """Upbit DataFrame을 캔들 모델로 변환하는 어댑터.

    Upbit 특징:
    - 컬럼명: 소문자 (open, high, low, close, volume, value)
    - 타임존: UTC (또는 timezone-naive → UTC로 간주)
    - 추가 컬럼: value (누적 거래 대금) - DB에 저장하지 않음
    - Interval: UpbitCandleInterval enum
    """

    def to_candle_models(
            self, df: pd.DataFrame, ticker_id: int, interval: object
    ) -> Sequence[CandleBase]:
        """Upbit DataFrame → 캔들 모델 리스트.

        타임존: 이미 UTC (또는 naive → UTC로 간주)
        Interval에 따라 CandleMinute1 또는 CandleDaily 반환
        """
        from src.upbit.upbit_api import UpbitCandleInterval

        if not isinstance(interval, UpbitCandleInterval):
            raise TypeError(f"Expected UpbitCandleInterval, got {type(interval)}")

        if interval == UpbitCandleInterval.MINUTE_1:
            return self._df_to_models(df, ticker_id, CandleMinute1)
        elif interval == UpbitCandleInterval.DAY:
            return self._df_to_models(df, ticker_id, CandleDaily)
        else:
            raise ValueError(f"Unsupported interval: {interval}. Only MINUTE_1 and DAY are supported.")

    @staticmethod
    def _df_to_models(df: pd.DataFrame, ticker_id: int, model_class: type[T]) -> list[T]:
        """Upbit DataFrame → 캔들 모델 리스트 (공통 로직).

        Args:
            df: Upbit DataFrame
            ticker_id: 티커 ID (Ticker 테이블의 PK)
            model_class: CandleMinute1 또는 CandleDaily 클래스

        Returns:
            캔들 모델 리스트
        """
        if df.empty:
            return []

        models = []
        for row in df.itertuples():
            kst_index = row.Index  # type: ignore[union-attr]
            if pd.isna(kst_index):
                continue

            # 인덱스는 KST timezone-aware, DB는 naive datetime을 기대
            kst_time_dt = kst_index.to_pydatetime()  # type: ignore[union-attr]
            if kst_time_dt.tzinfo is not None:
                kst_time_dt = kst_time_dt.replace(tzinfo=None)

            # timestamp 컬럼은 UTC timezone-aware
            utc_dt = row.timestamp.to_pydatetime()  # type: ignore[union-attr]
            # pandas가 timezone 정보를 제거한 경우, UTC로 명시적으로 설정
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=pytz.UTC)

            # CandleMinute1과 CandleDaily를 구분하여 생성
            if model_class == CandleMinute1:
                models.append(
                    model_class(
                        local_time=kst_time_dt,
                        ticker_id=ticker_id,
                        open=float(row.open),  # type: ignore[arg-type]
                        high=float(row.high),  # type: ignore[arg-type]
                        low=float(row.low),  # type: ignore[arg-type]
                        close=float(row.close),  # type: ignore[arg-type]
                        volume=float(row.volume),  # type: ignore[arg-type]
                        timestamp=utc_dt,
                    )
                )
            elif model_class == CandleDaily:
                models.append(
                    model_class(
                        date=kst_time_dt.date(),
                        ticker_id=ticker_id,
                        open=float(row.open),  # type: ignore[arg-type]
                        high=float(row.high),  # type: ignore[arg-type]
                        low=float(row.low),  # type: ignore[arg-type]
                        close=float(row.close),  # type: ignore[arg-type]
                        volume=float(row.volume),  # type: ignore[arg-type]
                    )
                )

        return models


class BinanceCandleAdapter(CandleDataAdapter):
    """Binance DataFrame을 캔들 모델로 변환하는 어댑터.

    Binance 특징:
    - 컬럼명: 대문자 (Open, High, Low, Close, Volume)
    - 타임존: UTC (또는 timezone-naive → UTC로 간주)
    - Interval: BinanceCandleInterval enum (이미 DB 형식과 동일)
    """

    def to_candle_models(
            self, df: "pd.DataFrame", ticker_id: int, interval: object
    ) -> Sequence[CandleBase]:
        """Binance DataFrame → 캔들 모델 리스트.

        컬럼명 변환: 대문자 → 소문자
        타임존: 이미 UTC (또는 naive → UTC로 간주)
        Interval에 따라 CandleMinute1 또는 CandleDaily 반환
        """
        from util.binance.model.candle import BinanceCandleInterval as BinanceInterval
        if not isinstance(interval, BinanceInterval):
            raise TypeError(f"Expected BinanceCandleInterval, got {type(interval)}")

        if interval == BinanceInterval.MINUTE_1:
            return self._to_minute1_models(df, ticker_id)
        elif interval == BinanceInterval.DAY_1:
            return self._to_daily_models(df, ticker_id)
        else:
            raise ValueError(f"Unsupported interval: {interval}. Only MINUTE_1 and DAY_1 are supported.")

    @staticmethod
    def _df_to_models(df: pd.DataFrame, ticker_id: int, model_class: type[T]) -> list[T]:
        """Binance DataFrame → 캔들 모델 리스트 (공통 로직).

        Args:
            df: Binance DataFrame (컬럼: Open, High, Low, Close, Volume, kst_time)
            ticker_id: 티커 ID (Ticker 테이블의 PK)
            model_class: CandleMinute1 또는 CandleDaily 클래스

        Returns:
            캔들 모델 리스트
        """
        if df.empty:
            return []

        models = []
        for row in df.itertuples():
            timestamp = row.Index  # type: ignore[union-attr]
            if pd.isna(timestamp):
                continue
            # Binance: 이미 UTC이거나 naive (UTC로 간주)
            if timestamp.tz is None:  # type: ignore[union-attr]
                utc_timestamp = timestamp.tz_localize("UTC")  # type: ignore[union-attr]
            else:
                utc_timestamp = timestamp.tz_convert("UTC")  # type: ignore[union-attr]

            utc_dt = utc_timestamp.to_pydatetime()  # type: ignore[union-attr]
            kst_time_dt = row.localtime.to_pydatetime()  # type: ignore[union-attr]
            # DB는 naive datetime을 기대하므로 timezone 정보 제거
            if kst_time_dt.tzinfo is not None:
                kst_time_dt = kst_time_dt.replace(tzinfo=None)

            # CandleMinute1과 CandleDaily를 구분하여 생성
            if model_class == CandleMinute1:
                models.append(
                    model_class(
                        timestamp=utc_dt,
                        local_time=kst_time_dt,
                        ticker_id=ticker_id,
                        open=float(row.Open),  # type: ignore[arg-type]
                        high=float(row.High),  # type: ignore[arg-type]
                        low=float(row.Low),  # type: ignore[arg-type]
                        close=float(row.Close),  # type: ignore[arg-type]
                        volume=float(row.Volume),  # type: ignore[arg-type]
                    )
                )
            elif model_class == CandleDaily:
                models.append(
                    model_class(
                        date=kst_time_dt.date(),
                        ticker_id=ticker_id,
                        open=float(row.Open),  # type: ignore[arg-type]
                        high=float(row.High),  # type: ignore[arg-type]
                        low=float(row.Low),  # type: ignore[arg-type]
                        close=float(row.Close),  # type: ignore[arg-type]
                        volume=float(row.Volume),  # type: ignore[arg-type]
                    )
                )

        return models

    def _to_minute1_models(self, df: pd.DataFrame, ticker_id: int) -> list[CandleMinute1]:
        """Binance DataFrame → list[CandleMinute1]."""
        return self._df_to_models(df, ticker_id, CandleMinute1)

    def _to_daily_models(self, df: pd.DataFrame, ticker_id: int) -> list[CandleDaily]:
        """Binance DataFrame → list[CandleDaily]."""
        return self._df_to_models(df, ticker_id, CandleDaily)


class HantuCandleAdapter(CandleDataAdapter):
    """Hantu (한국투자증권) DataFrame을 캔들 모델로 변환하는 어댑터.

    Hantu 특징:
    - 컬럼명: 한글 (시가, 고가, 저가, 종가, 거래량)
    - 타임존: KST (timezone-naive)
    - Interval: OverseasMinuteInterval (분봉) | OverseasCandlePeriod (일/주/월봉)
    """

    def to_candle_models(
            self,
            df: "pd.DataFrame",
            ticker_id: int,
            interval: object,
    ) -> Sequence[CandleBase]:
        """Hantu DataFrame → 캔들 모델 리스트.

        컬럼명 변환: 한글 → 영어
        타임존 변환: KST (naive) → UTC (aware)
        Interval에 따라 CandleMinute1 또는 CandleDaily 반환
        """
        from src.hantu.model.overseas.candle_period import OverseasCandlePeriod
        from src.hantu.model.overseas.minute_interval import OverseasMinuteInterval
        if not isinstance(interval, (OverseasMinuteInterval, OverseasCandlePeriod)):
            raise TypeError(f"Expected OverseasMinuteInterval or OverseasCandlePeriod, got {type(interval)}")

        # 한글 컬럼명을 영어로 rename
        df_renamed = df.rename(columns={
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume"
        })

        # Interval 체크: MIN_1 또는 DAILY만 지원
        if isinstance(interval, OverseasMinuteInterval) and interval == OverseasMinuteInterval.MIN_1:
            return self._to_minute1_models(df_renamed, ticker_id)
        elif isinstance(interval, OverseasCandlePeriod) and interval == OverseasCandlePeriod.DAILY:
            return self._to_daily_models(df_renamed, ticker_id)
        else:
            raise ValueError(
                f"Unsupported interval: {interval}. Only OverseasMinuteInterval.MIN_1 and OverseasCandlePeriod.DAILY are supported.")

    @staticmethod
    def _df_to_models(df: pd.DataFrame, ticker_id: int, model_class: type[T]) -> list[T]:
        """Hantu DataFrame → 캔들 모델 리스트 (공통 로직).

        Args:
            df: Hantu DataFrame (컬럼: open, high, low, close, volume, kst_time - 이미 영어로 rename됨)
            ticker_id: 티커 ID (Ticker 테이블의 PK)
            model_class: CandleMinute1 또는 CandleDaily 클래스

        Returns:
            캔들 모델 리스트
        """
        if df.empty:
            return []

        models = []
        for row in df.itertuples():
            timestamp = row.Index  # type: ignore[union-attr]
            if pd.isna(timestamp):
                continue
            # Hantu: KST naive → UTC aware
            utc_timestamp = timestamp.tz_localize("Asia/Seoul").tz_convert("UTC")  # type: ignore[union-attr]

            utc_dt = utc_timestamp.to_pydatetime()  # type: ignore[union-attr]
            kst_time_dt = row.localtime.to_pydatetime()  # type: ignore[union-attr]
            # DB는 naive datetime을 기대하므로 timezone 정보 제거
            if kst_time_dt.tzinfo is not None:
                kst_time_dt = kst_time_dt.replace(tzinfo=None)

            # CandleMinute1과 CandleDaily를 구분하여 생성
            if model_class == CandleMinute1:
                models.append(
                    model_class(
                        timestamp=utc_dt,
                        local_time=kst_time_dt,
                        ticker_id=ticker_id,
                        open=float(row.open),  # type: ignore[arg-type]
                        high=float(row.high),  # type: ignore[arg-type]
                        low=float(row.low),  # type: ignore[arg-type]
                        close=float(row.close),  # type: ignore[arg-type]
                        volume=float(row.volume),  # type: ignore[arg-type]
                    )
                )
            elif model_class == CandleDaily:
                models.append(
                    model_class(
                        date=kst_time_dt.date(),
                        ticker_id=ticker_id,
                        open=float(row.open),  # type: ignore[arg-type]
                        high=float(row.high),  # type: ignore[arg-type]
                        low=float(row.low),  # type: ignore[arg-type]
                        close=float(row.close),  # type: ignore[arg-type]
                        volume=float(row.volume),  # type: ignore[arg-type]
                    )
                )

        return models

    def _to_minute1_models(self, df: pd.DataFrame, ticker_id: int) -> list[CandleMinute1]:
        """Hantu DataFrame → list[CandleMinute1]."""
        return self._df_to_models(df, ticker_id, CandleMinute1)

    def _to_daily_models(self, df: pd.DataFrame, ticker_id: int) -> list[CandleDaily]:
        """Hantu DataFrame → list[CandleDaily]."""
        return self._df_to_models(df, ticker_id, CandleDaily)


class CommonCandleAdapter(CandleDataAdapter):
    """공통 캔들 어댑터 - CandleQueryService가 반환하는 표준 DataFrame 처리.

    CommonCandleSchema를 따르는 DataFrame을 캔들 모델로 변환합니다.
    CandleInterval을 사용하여 거래소에 독립적으로 동작합니다.

    특징:
    - 컬럼: timestamp, local_time, open, high, low, close, volume
    - Index: UTC DatetimeIndex
    - Interval: CandleInterval enum
    """

    def to_candle_models(
            self, df: pd.DataFrame, ticker_id: int, interval: object
    ) -> Sequence[CandleBase]:
        """CommonCandleSchema DataFrame → 캔들 모델 리스트.

        Args:
            df: CommonCandleSchema를 따르는 DataFrame
            ticker_id: 티커 ID
            interval: CandleInterval enum

        Returns:
            CandleMinute1 또는 CandleDaily 모델 리스트

        Raises:
            TypeError: interval이 CandleInterval이 아닌 경우
            ValueError: 지원하지 않는 interval인 경우
        """
        from src.common.candle_client import CandleInterval

        if not isinstance(interval, CandleInterval):
            raise TypeError(f"Expected CandleInterval, got {type(interval)}")

        if interval == CandleInterval.MINUTE_1:
            return self._to_minute1_models(df, ticker_id)
        elif interval == CandleInterval.DAY:
            return self._to_daily_models(df, ticker_id)
        else:
            raise ValueError(
                f"Unsupported interval: {interval}. "
                f"Only MINUTE_1 and DAY are supported."
            )

    def _to_minute1_models(
            self, df: pd.DataFrame, ticker_id: int
    ) -> list[CandleMinute1]:
        """CommonCandleSchema DataFrame → CandleMinute1 리스트."""
        if df.empty:
            return []

        models = []
        for row in df.itertuples():
            models.append(CandleMinute1(
                timestamp=row.timestamp,
                local_time=row.local_time,
                ticker_id=ticker_id,
                open=float(row.open),  # type: ignore[arg-type]
                high=float(row.high),  # type: ignore[arg-type]
                low=float(row.low),  # type: ignore[arg-type]
                close=float(row.close),  # type: ignore[arg-type]
                volume=float(row.volume),  # type: ignore[arg-type]
            ))
        return models

    def _to_daily_models(
            self, df: pd.DataFrame, ticker_id: int
    ) -> list[CandleDaily]:
        """CommonCandleSchema DataFrame → CandleDaily 리스트."""
        if df.empty:
            return []

        models = []
        for row in df.itertuples():
            # local_time에서 date 추출
            local_time = row.local_time
            if hasattr(local_time, 'date'):
                date = local_time.date()
            else:
                date = local_time

            models.append(CandleDaily(
                date=date,
                ticker_id=ticker_id,
                open=float(row.open),  # type: ignore[arg-type]
                high=float(row.high),  # type: ignore[arg-type]
                low=float(row.low),  # type: ignore[arg-type]
                close=float(row.close),  # type: ignore[arg-type]
                volume=float(row.volume),  # type: ignore[arg-type]
            ))
        return models
