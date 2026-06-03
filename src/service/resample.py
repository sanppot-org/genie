"""캔들·펀더멘털 시계열 기간 집계 (day / week / month)."""

from dataclasses import dataclass
from datetime import date
from itertools import groupby
from typing import Literal

from src.database.models import StockDailyCandle, StockFundamental

Interval = Literal["day", "week", "month"]


@dataclass(frozen=True)
class AggregatedCandle:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_value: int | None


def _bucket_key(d: date, interval: Interval) -> tuple[int, ...]:
    if interval == "month":
        return (d.year, d.month)
    # week
    iso = d.isocalendar()
    return (iso[0], iso[1])


def resample_candles(
    rows: list[StockDailyCandle] | list[StockDailyCandle | AggregatedCandle],
    interval: Interval,
) -> list[StockDailyCandle | AggregatedCandle]:
    """day → 원본 그대로, week/month → 버킷 집계 AggregatedCandle 리스트.

    입력은 원주가(StockDailyCandle) 또는 수정주가 치환(AggregatedCandle) 혼용 가능.
    """
    if not rows:
        return []
    if interval == "day":
        day_result: list[StockDailyCandle | AggregatedCandle] = list(rows)
        return day_result

    result: list[StockDailyCandle | AggregatedCandle] = []
    for _, bucket in groupby(rows, key=lambda r: _bucket_key(r.date, interval)):
        bucket_rows = list(bucket)
        trade_values = [r.trade_value for r in bucket_rows if r.trade_value is not None]
        result.append(
            AggregatedCandle(
                date=bucket_rows[-1].date,
                open=bucket_rows[0].open,
                high=max(r.high for r in bucket_rows),
                low=min(r.low for r in bucket_rows),
                close=bucket_rows[-1].close,
                volume=sum(r.volume for r in bucket_rows),
                trade_value=sum(trade_values) if trade_values else None,
            )
        )
    return result


def resample_fundamentals(
    rows: list[StockFundamental],
    interval: Interval,
) -> list[StockFundamental]:
    """day → 원본 그대로, week/month → 버킷 마지막 행(기말 스냅샷) 선택."""
    if not rows:
        return []
    if interval == "day":
        return list(rows)

    result: list[StockFundamental] = []
    for _, bucket in groupby(rows, key=lambda r: _bucket_key(r.date, interval)):
        bucket_rows = list(bucket)
        result.append(bucket_rows[-1])
    return result
