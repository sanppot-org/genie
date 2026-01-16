"""캔들 데이터 조회를 위한 공통 인터페이스 정의."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pandera.typing import DataFrame

from src.common.candle_schema import CommonCandleSchema

if TYPE_CHECKING:
    pass


class CandleInterval(StrEnum):
    """공통 캔들 간격.

    각 거래소별 지원 현황:
    - MINUTE_1:  Upbit O, Binance O, Hantu O
    - MINUTE_5:  Upbit O, Binance O, Hantu O
    - MINUTE_10: Upbit O, Binance X, Hantu O
    - MINUTE_30: Upbit O, Binance O, Hantu O
    - HOUR_1:    Upbit O, Binance O, Hantu O
    - HOUR_4:    Upbit O, Binance O, Hantu X
    - DAY:       Upbit O, Binance O, Hantu O
    - WEEK:      Upbit O, Binance O, Hantu O
    - MONTH:     Upbit O, Binance O, Hantu O
    """

    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_10 = "10m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"


@runtime_checkable
class CandleClient(Protocol):
    """캔들 데이터 조회 프로토콜.

    각 거래소 API가 이 프로토콜을 구현하여
    통일된 방식으로 캔들 데이터를 조회할 수 있습니다.

    반환되는 DataFrame 형식:
    - index: DatetimeIndex (UTC timezone-aware)
    - columns: open, high, low, close, volume
    - 정렬: 시간순 오름차순 (과거 → 최신)
    """

    def get_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int = 100,
            end_time: datetime | None = None,
    ) -> DataFrame[CommonCandleSchema]:
        """캔들 데이터 조회.

        Args:
            symbol: 거래소별 심볼 (예: "KRW-BTC", "BTCUSDT", "AAPL")
            interval: 캔들 간격 (CandleInterval)
            count: 조회할 캔들 개수 (기본값: 100)
            end_time: 종료 시간 (해당 시간 이전 데이터 조회, UTC)

        Returns:
            표준 캔들 DataFrame[CommonCandleSchema]
            - index: DatetimeIndex (UTC)
            - columns: open, high, low, close, volume
        """
        ...

    @property
    def supported_intervals(self) -> list[CandleInterval]:
        """지원하는 캔들 간격 목록."""
        ...
