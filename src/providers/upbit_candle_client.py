"""Upbit API를 CandleClient Protocol로 래핑하는 클라이언트."""

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
from pandera.typing import DataFrame

from src.common.candle_client import CandleInterval
from src.common.candle_schema import CommonCandleSchema
from src.upbit.upbit_api import UpbitAPI, UpbitCandleInterval

if TYPE_CHECKING:
    pass


class UpbitCandleClient:
    """Upbit API를 CandleClient Protocol로 래핑.

    기존 UpbitAPI를 수정하지 않고 CandleClient Protocol을 구현합니다.
    CandleInterval을 UpbitCandleInterval로 변환하고,
    반환되는 DataFrame을 표준 형식으로 정규화합니다.

    Example:
        >>> from src.upbit.upbit_api import UpbitAPI
        >>> from src.providers.upbit_candle_client import UpbitCandleClient
        >>> from src.common.candle_client import CandleInterval
        >>>
        >>> api = UpbitAPI()
        >>> client = UpbitCandleClient(api)
        >>> df = client.get_candles("KRW-BTC", CandleInterval.DAY, count=100)
    """

    _INTERVAL_MAP: dict[CandleInterval, UpbitCandleInterval] = {
        CandleInterval.MINUTE_1: UpbitCandleInterval.MINUTE_1,
        CandleInterval.MINUTE_5: UpbitCandleInterval.MINUTE_5,
        CandleInterval.MINUTE_10: UpbitCandleInterval.MINUTE_10,
        CandleInterval.MINUTE_30: UpbitCandleInterval.MINUTE_30,
        CandleInterval.HOUR_1: UpbitCandleInterval.MINUTE_60,
        CandleInterval.HOUR_4: UpbitCandleInterval.MINUTE_240,
        CandleInterval.DAY: UpbitCandleInterval.DAY,
        CandleInterval.WEEK: UpbitCandleInterval.WEEK,
        CandleInterval.MONTH: UpbitCandleInterval.MONTH,
    }

    def __init__(self, api: UpbitAPI) -> None:
        """UpbitCandleClient 초기화.

        Args:
            api: Upbit API 인스턴스
        """
        self._api = api

    def get_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int = 100,
            end_time: datetime | None = None,
    ) -> DataFrame[CommonCandleSchema]:
        """캔들 데이터 조회.

        Args:
            symbol: 마켓 ID (예: "KRW-BTC")
            interval: 캔들 간격 (CandleInterval)
            count: 조회할 캔들 개수 (기본값: 100)
            end_time: 종료 시간 (해당 시간 이전 데이터 조회, UTC)

        Returns:
            표준 캔들 DataFrame[CommonCandleSchema]
            - index: DatetimeIndex (UTC)
            - columns: open, high, low, close, volume
        """
        upbit_interval = self._to_upbit_interval(interval)

        df = self._api.get_candles(
            market=symbol,
            interval=upbit_interval,
            count=count,
            to=end_time,
        )

        standardized = self._standardize_dataframe(df)
        return CommonCandleSchema.validate(standardized)

    @property
    def supported_intervals(self) -> list[CandleInterval]:
        """지원하는 캔들 간격 목록."""
        return list(self._INTERVAL_MAP.keys())

    def _to_upbit_interval(self, interval: CandleInterval) -> UpbitCandleInterval:
        """CandleInterval을 UpbitCandleInterval로 변환.

        Args:
            interval: 공통 캔들 간격

        Returns:
            Upbit 캔들 간격

        Raises:
            ValueError: 지원하지 않는 간격인 경우
        """
        upbit_interval = self._INTERVAL_MAP.get(interval)
        if upbit_interval is None:
            raise ValueError(
                f"Upbit에서 지원하지 않는 간격입니다: {interval}. "
                f"지원 간격: {list(self._INTERVAL_MAP.keys())}"
            )
        return upbit_interval

    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame을 표준 형식으로 변환.

        - timestamp: UTC 시간
        - local_time: KST 로컬 시간
        - index를 UTC로 변환
        - OHLCV 컬럼 포함

        Args:
            df: Upbit API에서 반환된 DataFrame

        Returns:
            표준화된 DataFrame
        """
        if df.empty:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        df = df.copy()

        # 원본 index 저장 (KST local_time)
        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is not None:
                # timezone-aware인 경우 KST로 변환하여 local_time 저장
                local_index = df.index.tz_convert("Asia/Seoul")
            else:
                # timezone-naive인 경우 KST로 간주
                local_index = df.index.tz_localize("Asia/Seoul")

            # local_time: timezone 정보 제거 (naive datetime)
            df["local_time"] = local_index.tz_localize(None).to_pydatetime()

            # index를 UTC로 변환
            utc_index = local_index.tz_convert("UTC")
            df.index = utc_index

            # timestamp: UTC 시간 (timezone 정보 유지)
            df["timestamp"] = utc_index.to_pydatetime()

        # 필수 컬럼만 선택하여 반환
        return df[["timestamp", "local_time", "open", "high", "low", "close", "volume"]].copy()
