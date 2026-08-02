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


def test_adjusted_update_loads_only_fetched_date_range(db: Database, us_ticker: int, monkeypatch) -> None:
    """adj_* 갱신용 row 조회를 이번에 받은 봉 구간으로 한정한다 (종목 전체 이력 적재 금지).

    EOD 동기화는 5거래일만 받는데 종목 전체(수천~1만 행)를 매일 ORM 적재하면 순수 낭비다.
    구간 밖 기존 행이 로드되지 않음을 함께 검증한다.
    """
    seeded = [
        UsDailyBar(date=date(2020, 1, 2), open=10, high=11, low=9, close=10, volume=100, adj_close=10),
        UsDailyBar(date=date(2020, 1, 3), open=10, high=11, low=9, close=10, volume=100, adj_close=10),
    ]
    UsStockDailyCandleService(database=db, client=_client(seeded), throttle_sec=0).backfill(
        ["AAPL"], start=date(2020, 1, 1), now=date(2020, 1, 10),
    )

    calls: list[tuple[date | None, date | None]] = []
    original = StockDailyCandleRepository.find_by_ticker

    def spy(self, ticker_id, from_date=None, to_date=None):  # noqa: ANN001, ANN202
        calls.append((from_date, to_date))
        return original(self, ticker_id, from_date=from_date, to_date=to_date)

    monkeypatch.setattr(StockDailyCandleRepository, "find_by_ticker", spy)

    recent = [UsDailyBar(date=date(2024, 3, 5), open=20, high=21, low=19, close=20, volume=200, adj_close=10)]
    service = UsStockDailyCandleService(database=db, client=_client(recent), throttle_sec=0)
    service.sync_recent(lookback_days=5, now=date(2024, 3, 6))

    assert calls == [(date(2024, 3, 5), date(2024, 3, 5))]  # 전체 이력(None, None) 아님

    session = db.get_session()
    try:
        rows = {r.date: r for r in StockDailyCandleRepository(session).find_by_ticker(us_ticker)}
    finally:
        session.close()
    assert rows[date(2024, 3, 5)].adj_close == 10        # factor=0.5 적용됨
    assert rows[date(2024, 3, 5)].adj_open == 10
    assert rows[date(2020, 1, 2)].adj_close == 10        # 구간 밖 기존 행 불변
    assert len(rows) == 3


def test_backfill_targets_both_us_stock_and_us_etf(db: Database, us_ticker: int) -> None:
    """대상 선정이 US_STOCK과 US_ETF active FDR ticker를 모두 포함한다."""
    session = db.get_session()
    try:
        TickerRepository(session).save(Ticker(
            ticker="TQQQ", name="ProShares UltraPro QQQ",
            asset_type=AssetType.US_ETF, data_source=DataSource.FDR.value, exchange=None,
        ))
        session.commit()
    finally:
        session.close()

    bar = [UsDailyBar(date=date(2024, 1, 2), open=10, high=11, low=9, close=10, volume=100, adj_close=10)]
    service = UsStockDailyCandleService(database=db, client=_client(bar), throttle_sec=0)
    result = service.backfill(start=date(2024, 1, 1), now=date(2024, 1, 10))

    assert result.ticker_count == 2  # AAPL(US_STOCK) + TQQQ(US_ETF)
    assert result.tickers_upserted == 2
