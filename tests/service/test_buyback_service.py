"""Tests for BuybackService — 점수 판정."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockBuybackEvent, Ticker
from src.database.stock_buyback_event_repository import StockBuybackEventRepository
from src.database.ticker_repository import TickerRepository
from src.service.buyback_service import BuybackService


@pytest.fixture
def ticker(session: Session) -> Ticker:
    repo = TickerRepository(session)
    return repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))


def _add_event(
        session: Session, ticker_id: int, rcept_no: str,
        event_type: str, resolution_date: date,
) -> None:
    repo = StockBuybackEventRepository(session)
    repo.bulk_upsert([
        StockBuybackEvent(
            ticker_id=ticker_id, rcept_no=rcept_no,
            event_type=event_type, resolution_date=resolution_date,
            planned_shares=None, planned_amount=None,
            period_start=None, period_end=None, purpose=None,
        ),
    ])


class TestIsRegularBuyback:
    def test_recent_acquisition_within_window_returns_true(
            self, session: Session, ticker: Ticker,
    ) -> None:
        """최근 1년 내 ACQUISITION 1건 있으면 True."""
        _add_event(session, ticker.id, "A1", "ACQUISITION", date(2026, 1, 15))
        service = BuybackService(StockBuybackEventRepository(session))

        assert service.is_regular_buyback(ticker.id, date(2026, 5, 18)) is True

    def test_no_event_returns_false(
            self, session: Session, ticker: Ticker,
    ) -> None:
        """이벤트가 전혀 없으면 False."""
        service = BuybackService(StockBuybackEventRepository(session))

        assert service.is_regular_buyback(ticker.id, date(2026, 5, 18)) is False

    def test_acquisition_older_than_window_returns_false(
            self, session: Session, ticker: Ticker,
    ) -> None:
        """1년 이전 ACQUISITION만 있으면 False."""
        _add_event(session, ticker.id, "A1", "ACQUISITION", date(2024, 1, 1))
        service = BuybackService(StockBuybackEventRepository(session))

        assert service.is_regular_buyback(ticker.id, date(2026, 5, 18)) is False

    def test_only_disposal_returns_false(
            self, session: Session, ticker: Ticker,
    ) -> None:
        """처분 공시만 있으면 False (취득만 점수 인정)."""
        _add_event(session, ticker.id, "D1", "DISPOSAL", date(2026, 1, 15))
        service = BuybackService(StockBuybackEventRepository(session))

        assert service.is_regular_buyback(ticker.id, date(2026, 5, 18)) is False

    def test_custom_window_years(
            self, session: Session, ticker: Ticker,
    ) -> None:
        """window_years를 늘리면 더 오래된 이벤트도 인정."""
        _add_event(session, ticker.id, "A1", "ACQUISITION", date(2023, 6, 1))
        service = BuybackService(StockBuybackEventRepository(session))

        assert service.is_regular_buyback(ticker.id, date(2026, 5, 18)) is False
        assert service.is_regular_buyback(ticker.id, date(2026, 5, 18), window_years=3) is True
