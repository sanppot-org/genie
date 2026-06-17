"""UsStockDailyCandleService 통합 테스트 (인메모리 DB + UsStockDailyClient mock)."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.us_stock_daily_client import UsDailyBar, UsStockDailyClient
from src.service.us_stock_daily_candle_service import UsStockDailyCandleService


@pytest.fixture
def us_ticker(db: Database) -> int:
    session = db.get_session()
    try:
        t = TickerRepository(session).save(Ticker(
            ticker="AAPL", name="Apple Inc",
            asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value, exchange="NAS",
        ))
        session.commit()
        return t.id
    finally:
        session.close()


def _client(bars: list[UsDailyBar]) -> MagicMock:
    m = MagicMock(spec=UsStockDailyClient)
    m.fetch.return_value = bars
    return m


def test_backfill_upserts_raw_and_adjusted(db: Database, us_ticker: int) -> None:
    """원주가 OHLCV upsert + factor(AdjClose/Close)로 adj_* 복원."""
    bars = [
        # close=200, adj_close=100 → factor=0.5
        UsDailyBar(date=date(2024, 1, 2), open=210, high=220, low=190, close=200, volume=1_000_000, adj_close=100),
        # factor=1.0 (수정 없음)
        UsDailyBar(date=date(2024, 1, 3), open=205, high=215, low=200, close=210, volume=900_000, adj_close=210),
    ]
    service = UsStockDailyCandleService(database=db, client=_client(bars), throttle_sec=0)

    result = service.backfill(["AAPL"], start=date(2024, 1, 1), now=date(2024, 1, 10))

    assert result.rows_upserted == 2
    assert result.tickers_upserted == 1

    session = db.get_session()
    try:
        rows = {r.date: r for r in StockDailyCandleRepository(session).find_by_ticker(us_ticker)}
    finally:
        session.close()
    r1 = rows[date(2024, 1, 2)]
    assert r1.close == 200 and r1.open == 210      # 원주가 보존
    assert r1.adj_close == 100                      # 수정 종가
    assert r1.adj_open == 105 and r1.adj_high == 110 and r1.adj_low == 95  # OHLC * 0.5
    assert r1.adj_volume is None                    # adj_volume은 NULL (Spec §6)
    r2 = rows[date(2024, 1, 3)]
    assert r2.adj_close == 210 and r2.adj_open == 205  # factor=1.0
    assert r2.adj_volume is None


def test_backfill_skips_empty_response(db: Database, us_ticker: int) -> None:
    service = UsStockDailyCandleService(database=db, client=_client([]), throttle_sec=0)
    result = service.backfill(["AAPL"], start=date(2024, 1, 1), now=date(2024, 1, 10))
    assert result.rows_upserted == 0
    assert result.tickers_upserted == 0


def test_backfill_continues_on_one_ticker_failure(db: Database, us_ticker: int) -> None:
    """한 종목 client 예외가 배치를 막지 않음 (failed로 집계)."""
    client = MagicMock(spec=UsStockDailyClient)
    client.fetch.side_effect = RuntimeError("network down")
    service = UsStockDailyCandleService(database=db, client=client, throttle_sec=0)
    result = service.backfill(["AAPL"], start=date(2024, 1, 1), now=date(2024, 1, 10))
    assert result.failed == 1
    assert "AAPL" in result.failed_tickers
