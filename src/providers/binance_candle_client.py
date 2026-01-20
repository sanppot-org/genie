"""Binance API를 CandleClient Protocol로 래핑하는 클라이언트."""

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
from pandera.typing import DataFrame

from src.common.candle_client import CandleClient, CandleInterval
from src.common.candle_schema import CommonCandleSchema
from util.binance.binance_api import BinanceAPI
from util.binance.model.candle import BinanceCandleData, BinanceCandleInterval

if TYPE_CHECKING:
    pass


class BinanceCandleClient(CandleClient):
    """Binance API를 CandleClient Protocol로 래핑.

    기존 BinanceAPI를 수정하지 않고 CandleClient Protocol을 구현합니다.
    CandleInterval을 BinanceCandleInterval로 변환하고,
    반환되는 캔들 데이터를 표준 DataFrame 형식으로 정규화합니다.

    Example:
        >>> from util.binance.binance_api import BinanceAPI
        >>> from src.providers.binance_candle_client import BinanceCandleClient
        >>> from src.common.candle_client import CandleInterval
        >>>
        >>> api = BinanceAPI()
        >>> client = BinanceCandleClient(api)
        >>> df = client.get_candles("BTCUSDT", CandleInterval.DAY, count=100)
    """

    _INTERVAL_MAP: dict[CandleInterval, BinanceCandleInterval] = {
        CandleInterval.MINUTE_1: BinanceCandleInterval.MINUTE_1,
        CandleInterval.MINUTE_5: BinanceCandleInterval.MINUTE_5,
        CandleInterval.MINUTE_30: BinanceCandleInterval.MINUTE_30,
        CandleInterval.HOUR_1: BinanceCandleInterval.HOUR_1,
        CandleInterval.HOUR_4: BinanceCandleInterval.HOUR_4,
        CandleInterval.DAY: BinanceCandleInterval.DAY_1,
        CandleInterval.WEEK: BinanceCandleInterval.WEEK_1,
        CandleInterval.MONTH: BinanceCandleInterval.MONTH_1,
    }

    def __init__(self, api: BinanceAPI) -> None:
        """BinanceCandleClient 초기화.

        Args:
            api: Binance API 인스턴스
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
            symbol: 심볼 (예: "BTCUSDT")
            interval: 캔들 간격 (CandleInterval)
            count: 조회할 캔들 개수 (기본값: 100, 최대: 1000)
            end_time: 종료 시간 (해당 시간 이전 데이터 조회, UTC)

        Returns:
            표준 캔들 DataFrame[CommonCandleSchema]
            - index: DatetimeIndex (UTC)
            - columns: open, high, low, close, volume
        """
        binance_interval = self._to_binance_interval(interval)

        candles = self._api.get_candles(
            symbol=symbol,
            interval=binance_interval,
            limit=min(count, 1000),  # 최대 1000개
            end_time=end_time,
        )

        df = self._to_dataframe(candles)
        return CommonCandleSchema.validate(df)

    @property
    def supported_intervals(self) -> list[CandleInterval]:
        """지원하는 캔들 간격 목록."""
        return list(self._INTERVAL_MAP.keys())

    def _to_binance_interval(self, interval: CandleInterval) -> BinanceCandleInterval:
        """CandleInterval을 BinanceCandleInterval로 변환.

        Args:
            interval: 공통 캔들 간격

        Returns:
            Binance 캔들 간격

        Raises:
            ValueError: 지원하지 않는 간격인 경우
        """
        binance_interval = self._INTERVAL_MAP.get(interval)
        if binance_interval is None:
            raise ValueError(
                f"Binance에서 지원하지 않는 간격입니다: {interval}. "
                f"지원 간격: {list(self._INTERVAL_MAP.keys())}"
            )
        return binance_interval

    @staticmethod
    def _to_dataframe(candles: list[BinanceCandleData]) -> pd.DataFrame:
        """캔들 데이터 리스트를 DataFrame으로 변환.

        Args:
            candles: Binance 캔들 데이터 리스트

        Returns:
            표준화된 DataFrame
        """
        if not candles:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        data = []
        for candle in candles:
            # Binance는 UTC 기준이므로 local_time도 UTC와 동일
            data.append({
                "timestamp": candle.open_time,
                "local_time": candle.open_time.replace(tzinfo=None),  # naive datetime
                "open": candle.open_price,
                "high": candle.high_price,
                "low": candle.low_price,
                "close": candle.close_price,
                "volume": candle.volume,
            })

        df = pd.DataFrame(data)
        df = df.set_index(pd.DatetimeIndex(df["timestamp"]))
        df = df.sort_index(ascending=True)

        return df[["timestamp", "local_time", "open", "high", "low", "close", "volume"]]
