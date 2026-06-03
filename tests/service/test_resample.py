"""Tests for resample — candle/fundamental interval aggregation."""

from datetime import date
from unittest.mock import MagicMock

from src.database.models import StockDailyCandle, StockFundamental
from src.service.resample import AggregatedCandle, resample_candles, resample_fundamentals


def _candle(d: date, open_: float, high: float, low: float, close: float, volume: int, trade_value: int | None = None) -> StockDailyCandle:
    c = MagicMock(spec=StockDailyCandle)
    c.date = d
    c.open = open_
    c.high = high
    c.low = low
    c.close = close
    c.volume = volume
    c.trade_value = trade_value
    return c


def _fundamental(d: date) -> StockFundamental:
    f = MagicMock(spec=StockFundamental)
    f.date = d
    return f


class TestResampleCandles:
    def test_day_passthrough(self) -> None:
        rows = [
            _candle(date(2024, 1, 2), 100, 110, 90, 105, 1000),
            _candle(date(2024, 1, 3), 105, 115, 100, 110, 2000),
        ]
        result = resample_candles(rows, "day")
        assert result is not rows  # new list
        assert len(result) == 2
        assert result[0].date == date(2024, 1, 2)

    def test_month_두달_집계(self) -> None:
        # January: 3 rows, February: 2 rows
        rows = [
            _candle(date(2024, 1, 2),  100, 120, 90,  115, 1000, 100_000),
            _candle(date(2024, 1, 15), 115, 125, 110, 118, 2000, 200_000),
            _candle(date(2024, 1, 31), 118, 130, 115, 128, 3000, None),
            _candle(date(2024, 2, 1),  128, 135, 120, 130, 1500, 150_000),
            _candle(date(2024, 2, 29), 130, 140, 125, 138, 2500, 250_000),
        ]
        result = resample_candles(rows, "month")
        assert len(result) == 2

        jan: AggregatedCandle = result[0]  # type: ignore[assignment]
        assert jan.date == date(2024, 1, 31)
        assert jan.open == 100
        assert jan.high == 130
        assert jan.low == 90
        assert jan.close == 128
        assert jan.volume == 1000 + 2000 + 3000
        # trade_value: 100_000 + 200_000 (None skipped)
        assert jan.trade_value == 300_000

        feb: AggregatedCandle = result[1]  # type: ignore[assignment]
        assert feb.date == date(2024, 2, 29)
        assert feb.open == 128
        assert feb.high == 140
        assert feb.low == 120
        assert feb.close == 138
        assert feb.volume == 1500 + 2500
        assert feb.trade_value == 400_000

    def test_month_trade_value_전부_None(self) -> None:
        rows = [
            _candle(date(2024, 3, 1), 100, 110, 90, 105, 1000, None),
            _candle(date(2024, 3, 5), 105, 115, 100, 110, 2000, None),
        ]
        result = resample_candles(rows, "month")
        assert len(result) == 1
        assert result[0].trade_value is None  # type: ignore[union-attr]

    def test_빈_입력(self) -> None:
        assert resample_candles([], "month") == []

    def test_week_집계(self) -> None:
        # 2024-01-01 (Mon, ISO week 1) and 2024-01-08 (Mon, ISO week 2)
        rows = [
            _candle(date(2024, 1, 1), 100, 110, 90, 105, 500),
            _candle(date(2024, 1, 3), 105, 115, 100, 112, 700),
            _candle(date(2024, 1, 8), 112, 120, 108, 118, 600),
        ]
        result = resample_candles(rows, "week")
        assert len(result) == 2
        w1: AggregatedCandle = result[0]  # type: ignore[assignment]
        assert w1.open == 100
        assert w1.high == 115
        assert w1.low == 90
        assert w1.close == 112
        assert w1.volume == 1200
        assert w1.date == date(2024, 1, 3)


class TestResampleFundamentals:
    def test_day_passthrough(self) -> None:
        rows = [_fundamental(date(2024, 1, 2)), _fundamental(date(2024, 1, 3))]
        result = resample_fundamentals(rows, "day")
        assert len(result) == 2

    def test_month_마지막행_선택(self) -> None:
        jan_first = _fundamental(date(2024, 1, 5))
        jan_last = _fundamental(date(2024, 1, 31))
        feb_last = _fundamental(date(2024, 2, 29))
        rows = [jan_first, jan_last, feb_last]

        result = resample_fundamentals(rows, "month")
        assert len(result) == 2
        assert result[0] is jan_last
        assert result[1] is feb_last

    def test_빈_입력(self) -> None:
        assert resample_fundamentals([], "month") == []
