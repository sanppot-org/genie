"""Tests for StockFundamentalRepository."""

from collections.abc import Generator
from datetime import date
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.database.database import Database
from src.database.models import StockFundamental, Ticker
from src.database.stock_fundamental_repository import StockFundamentalRepository


@pytest.fixture
def fundamental_repo(session: Session) -> StockFundamentalRepository:
    """StockFundamental Repository fixture."""
    return StockFundamentalRepository(session)


@pytest.fixture
def stock_ticker(session: Session, db: Database) -> Generator[Ticker, Any, None]:
    """샘플 KR 주식 Ticker. (sample_ticker는 KRW-BTC 암호화폐라 별도 분리)"""
    from src.common.data_adapter import DataSource
    from src.constants import AssetType
    from src.database.ticker_repository import TickerRepository

    ticker = Ticker(ticker="005930", name="삼성전자", asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value)
    TickerRepository(session).save(ticker)
    yield ticker


class TestStockFundamentalRepository:
    """StockFundamentalRepository 테스트."""

    def test_bulk_upsert_inserts_and_overwrites_on_conflict(
            self,
            fundamental_repo: StockFundamentalRepository,
            stock_ticker: Ticker,
    ) -> None:
        """동일 (date, ticker_id)에 대해 두 번째 호출이 첫 번째 값을 덮어쓰고 row 수는 그대로."""
        # Given
        target_date = date(2024, 1, 2)
        first = StockFundamental(
            ticker_id=stock_ticker.id,
            date=target_date,
            bps=50000, per=10.0, pbr=1.2, eps=5000, div=2.5, dps=1000,
        )
        fundamental_repo.bulk_upsert([first])

        # When - 같은 키, 다른 값
        second = StockFundamental(
            ticker_id=stock_ticker.id,
            date=target_date,
            bps=60000, per=12.5, pbr=1.4, eps=4800, div=2.8, dps=1100,
        )
        fundamental_repo.bulk_upsert([second])

        # Then
        rows = fundamental_repo.find_by_date(target_date)
        assert len(rows) == 1
        assert rows[0].bps == 60000
        assert rows[0].per == 12.5
        assert rows[0].pbr == 1.4

    def test_find_by_ticker_returns_range_ordered_ascending(
            self,
            fundamental_repo: StockFundamentalRepository,
            stock_ticker: Ticker,
    ) -> None:
        """from_date/to_date 범위 슬라이스 + date 오름차순."""
        # Given
        entities = [
            StockFundamental(ticker_id=stock_ticker.id, date=date(2024, 1, d), per=float(d))
            for d in (1, 2, 3)
        ]
        fundamental_repo.bulk_upsert(entities)

        # When - 가운데 하루만 포함하는 범위
        result = fundamental_repo.find_by_ticker(
            stock_ticker.id, from_date=date(2024, 1, 2), to_date=date(2024, 1, 2)
        )

        # Then
        assert len(result) == 1
        assert result[0].date == date(2024, 1, 2)
        assert result[0].per == 2.0

        # When - 전체 범위 (오름차순 검증)
        all_rows = fundamental_repo.find_by_ticker(stock_ticker.id)

        # Then
        assert [r.date for r in all_rows] == [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
