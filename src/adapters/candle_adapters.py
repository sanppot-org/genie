"""Candle data adapter implementations for different sources."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

import pandas as pd
from pytz import UTC

from src.common.data_adapter import CandleDataAdapter
from src.constants import KST
from src.database.models import CandleBase, CandleDaily, CandleMinute1

T = TypeVar("T", bound=CandleBase)

if TYPE_CHECKING:
    pass


class UpbitCandleAdapter(CandleDataAdapter):
    """Upbit DataFrame을 캔들 모델로 변환하는 어댑터.

    Upbit 특징:
    - 컬럼명: 소문자 (open, high, low, close, volume, value)
    - 타임존: KST (timezone-naive)
    - 추가 컬럼: value (누적 거래 대금) - DB에 저장하지 않음
    - Interval: UpbitCandleInterval enum
    """

    def to_candle_models(
            self, df: pd.DataFrame, ticker: str, interval: object
    ) -> Sequence[CandleBase]:
        """Upbit DataFrame → 캔들 모델 리스트.

        타임존 변환: KST (naive) → UTC (aware)
        Interval에 따라 CandleMinute1 또는 CandleDaily 반환
        """
        from src.upbit.upbit_api import UpbitCandleInterval

        if not isinstance(interval, UpbitCandleInterval):
            raise TypeError(f"Expected UpbitCandleInterval, got {type(interval)}")

        if interval == UpbitCandleInterval.MINUTE_1:
            return self._df_to_models(df, ticker, CandleMinute1)
        elif interval == UpbitCandleInterval.DAY:
            return self._df_to_models(df, ticker, CandleDaily)
        else:
            raise ValueError(f"Unsupported interval: {interval}. Only MINUTE_1 and DAY are supported.")

    @staticmethod
    def _df_to_models(df: pd.DataFrame, ticker: str, model_class: type[T]) -> list[T]:
        """Upbit DataFrame → 캔들 모델 리스트 (공통 로직).

        Args:
            df: Upbit DataFrame
            ticker: 티커
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
            utc_timestamp = timestamp.tz_localize(KST).tz_convert(UTC)  # type: ignore[union-attr]

            models.append(
                model_class(
                    timestamp=utc_timestamp.to_pydatetime(),  # type: ignore[union-attr]
                    ticker=ticker,
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
            self, df: "pd.DataFrame", ticker: str, interval: object
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
            return self._to_minute1_models(df, ticker)
        elif interval == BinanceInterval.DAY_1:
            return self._to_daily_models(df, ticker)
        else:
            raise ValueError(f"Unsupported interval: {interval}. Only MINUTE_1 and DAY_1 are supported.")

    @staticmethod
    def _df_to_models(df: pd.DataFrame, ticker: str, model_class: type[T]) -> list[T]:
        """Binance DataFrame → 캔들 모델 리스트 (공통 로직).

        Args:
            df: Binance DataFrame (컬럼: Open, High, Low, Close, Volume)
            ticker: 티커
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

            models.append(
                model_class(
                    timestamp=utc_timestamp.to_pydatetime(),  # type: ignore[union-attr]
                    ticker=ticker,
                    open=float(row.Open),  # type: ignore[arg-type]
                    high=float(row.High),  # type: ignore[arg-type]
                    low=float(row.Low),  # type: ignore[arg-type]
                    close=float(row.Close),  # type: ignore[arg-type]
                    volume=float(row.Volume),  # type: ignore[arg-type]
                )
            )

        return models

    def _to_minute1_models(self, df: pd.DataFrame, ticker: str) -> list[CandleMinute1]:
        """Binance DataFrame → list[CandleMinute1]."""
        return self._df_to_models(df, ticker, CandleMinute1)

    def _to_daily_models(self, df: pd.DataFrame, ticker: str) -> list[CandleDaily]:
        """Binance DataFrame → list[CandleDaily]."""
        return self._df_to_models(df, ticker, CandleDaily)


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
            ticker: str,
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
            return self._to_minute1_models(df_renamed, ticker)
        elif isinstance(interval, OverseasCandlePeriod) and interval == OverseasCandlePeriod.DAILY:
            return self._to_daily_models(df_renamed, ticker)
        else:
            raise ValueError(f"Unsupported interval: {interval}. Only OverseasMinuteInterval.MIN_1 and OverseasCandlePeriod.DAILY are supported.")

    @staticmethod
    def _df_to_models(df: pd.DataFrame, ticker: str, model_class: type[T]) -> list[T]:
        """Hantu DataFrame → 캔들 모델 리스트 (공통 로직).

        Args:
            df: Hantu DataFrame (컬럼: open, high, low, close, volume - 이미 영어로 rename됨)
            ticker: 티커
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

            models.append(
                model_class(
                    timestamp=utc_timestamp.to_pydatetime(),  # type: ignore[union-attr]
                    ticker=ticker,
                    open=float(row.open),  # type: ignore[arg-type]
                    high=float(row.high),  # type: ignore[arg-type]
                    low=float(row.low),  # type: ignore[arg-type]
                    close=float(row.close),  # type: ignore[arg-type]
                    volume=float(row.volume),  # type: ignore[arg-type]
                )
            )

        return models

    def _to_minute1_models(self, df: pd.DataFrame, ticker: str) -> list[CandleMinute1]:
        """Hantu DataFrame → list[CandleMinute1]."""
        return self._df_to_models(df, ticker, CandleMinute1)

    def _to_daily_models(self, df: pd.DataFrame, ticker: str) -> list[CandleDaily]:
        """Hantu DataFrame → list[CandleDaily]."""
        return self._df_to_models(df, ticker, CandleDaily)
