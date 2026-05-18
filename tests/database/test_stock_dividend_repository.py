"""Tests for StockDividendRepository."""

from collections.abc import Generator
from datetime import date
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDividend, Ticker
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.ticker_repository import TickerRepository


@pytest.fixture
def dividend_repo(session: Session) -> StockDividendRepository:
    return StockDividendRepository(session)


@pytest.fixture
def stock_ticker(session: Session) -> Generator[Ticker, Any, None]:
    ticker = Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    )
    TickerRepository(session).save(ticker)
    yield ticker


class TestStockDividendRepository:
    def test_bulk_upsert_overwrites_on_conflict(
            self, dividend_repo: StockDividendRepository, stock_ticker: Ticker,
    ) -> None:
        """동일 (ticker_id, record_date, kind) 재호출 시 row 수 유지 + 값 덮어쓰기."""
        first = StockDividend(
            ticker_id=stock_ticker.id, record_date=date(2024, 12, 27),
            pay_date=date(2025, 4, 17), dps=361.0, kind="SETTLE",
            fiscal_year=2024,
        )
        dividend_repo.bulk_upsert([first])

        second = StockDividend(
            ticker_id=stock_ticker.id, record_date=date(2024, 12, 27),
            pay_date=date(2025, 4, 17), dps=400.0, kind="SETTLE",
            fiscal_year=2024,
        )
        dividend_repo.bulk_upsert([second])

        rows = dividend_repo.find_by_ticker(stock_ticker.id)
        assert len(rows) == 1
        assert rows[0].dps == 400.0

    def test_find_by_ticker_returns_range_ordered_ascending(
            self, dividend_repo: StockDividendRepository, stock_ticker: Ticker,
    ) -> None:
        """from_date/to_date 슬라이스 + record_date 오름차순."""
        entities = [
            StockDividend(
                ticker_id=stock_ticker.id, record_date=date(2024, m, 1),
                dps=100.0 * m, kind="INTERIM", fiscal_year=2024,
            )
            for m in (3, 6, 9, 12)
        ]
        dividend_repo.bulk_upsert(entities)

        result = dividend_repo.find_by_ticker(
            stock_ticker.id, from_date=date(2024, 6, 1), to_date=date(2024, 9, 30),
        )

        assert [r.record_date for r in result] == [date(2024, 6, 1), date(2024, 9, 1)]
