"""KR 주식 일봉 읽기 서비스 — ticker 코드 → 일자 범위 시계열."""

from datetime import date
from typing import Literal

from src.database.models import StockDailyCandle, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.service.exceptions import ExceptionCode, GenieError
from src.service.resample import AggregatedCandle, Interval, resample_candles

PriceMode = Literal["raw", "adjusted"]


def _to_adjusted(c: StockDailyCandle) -> AggregatedCandle:
    """원주가 row를 수정주가 값으로 치환한 AggregatedCandle로 변환.

    adj_* 미백필(NULL) row는 원주가로 폴백 → 액면분할 종목만 보정되고 나머지는 동일.
    거래대금(trade_value)은 수정주가 소스 미제공이라 원본 유지.
    """
    return AggregatedCandle(
        date=c.date,
        open=c.adj_open if c.adj_open is not None else c.open,
        high=c.adj_high if c.adj_high is not None else c.high,
        low=c.adj_low if c.adj_low is not None else c.low,
        close=c.adj_close if c.adj_close is not None else c.close,
        volume=c.adj_volume if c.adj_volume is not None else c.volume,
        trade_value=c.trade_value,
    )


class StockDailyCandleService:
    """KR 주식 일봉 시계열 조회 (쓰기는 `DailyCandleSyncService`)."""

    def __init__(
            self,
            ticker_repository: TickerRepository,
            daily_candle_repository: StockDailyCandleRepository,
    ) -> None:
        self._tickers = ticker_repository
        self._candles = daily_candle_repository

    def get_time_series(
            self,
            ticker_code: str,
            from_date: date | None,
            to_date: date | None,
            interval: Interval = "day",
            price: PriceMode = "raw",
    ) -> tuple[Ticker, list[StockDailyCandle | AggregatedCandle]]:
        """ticker 코드로 종목 + 일자 범위 일봉 반환. 종목 미발견 시 404.

        price="adjusted"면 수정주가(adj_*, 없으면 원주가 폴백)로 치환 후 집계.
        """
        ticker = self._tickers.find_by_ticker(ticker_code)
        if ticker is None:
            raise GenieError(code=ExceptionCode.NOT_FOUND, id=ticker_code)
        rows = self._candles.find_by_ticker(ticker.id, from_date, to_date)
        source: list[StockDailyCandle | AggregatedCandle]
        if price == "adjusted":
            source = [_to_adjusted(r) for r in rows]
        else:
            source = list(rows)
        resampled: list[StockDailyCandle | AggregatedCandle] = resample_candles(source, interval)
        return ticker, resampled
