"""Tests for BuybackSyncService."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker
from src.database.stock_buyback_event_repository import StockBuybackEventRepository
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import BuybackEvent, DartCompanyClient
from src.service.buyback_sync_service import BuybackSyncService


@pytest.fixture
def kr_stock_ticker(session: Session) -> Ticker:
    repo = TickerRepository(session)
    return repo.save(Ticker(
        ticker="035420", name="NAVER",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))


def _make_service(
        session: Session,
        responses: dict[str, list[BuybackEvent] | Exception],
) -> BuybackSyncService:
    client = MagicMock(spec=DartCompanyClient)

    def fake_fetch(stock_code: str, from_date: date, to_date: date) -> list[BuybackEvent]:
        res = responses.get(stock_code, [])
        if isinstance(res, Exception):
            raise res
        return res

    client.fetch_buyback_events.side_effect = fake_fetch
    return BuybackSyncService(
        client=client,
        ticker_repository=TickerRepository(session),
        buyback_event_repository=StockBuybackEventRepository(session),
    )


class TestBuybackSyncService:
    def test_sync_upserts_acquisition_and_disposal(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """ACQUISITION + DISPOSAL 이벤트 모두 적재."""
        responses = {
            "035420": [
                BuybackEvent(
                    stock_code="035420", rcept_no="20240930000001",
                    event_type="ACQUISITION", resolution_date=date(2024, 9, 27),
                    planned_shares=2_347_500, planned_amount=401_187_750_000,
                    period_start=date(2024, 10, 2), period_end=date(2024, 12, 28),
                    purpose="이익소각",
                ),
                BuybackEvent(
                    stock_code="035420", rcept_no="20240326000771",
                    event_type="DISPOSAL", resolution_date=date(2024, 3, 26),
                    planned_shares=171_370, planned_amount=32_217_560_000,
                    period_start=date(2024, 3, 26), period_end=date(2024, 4, 26),
                    purpose="임직원 보상",
                ),
            ],
        }
        service = _make_service(session, responses)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.tickers == 1
        assert result.received == 2
        assert result.upserted == 2
        assert result.skipped_failure == 0

        rows = StockBuybackEventRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert {r.event_type for r in rows} == {"ACQUISITION", "DISPOSAL"}
        assert {r.rcept_no for r in rows} == {"20240930000001", "20240326000771"}

    def test_sync_counts_failure(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """클라이언트 예외는 skipped_failure로 카운트."""
        service = _make_service(session, {"035420": RuntimeError("boom")})

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 0
        assert result.skipped_failure == 1

    def test_sync_is_idempotent(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """같은 rcept_no는 재호출 시에도 row 1개 유지, 최신 값으로 덮어쓰기."""
        first = BuybackEvent(
            stock_code="035420", rcept_no="20240930000001",
            event_type="ACQUISITION", resolution_date=date(2024, 9, 27),
            planned_shares=100, planned_amount=1_000_000,
            period_start=None, period_end=None, purpose="이익소각",
        )
        _make_service(session, {"035420": [first]}).sync(date(2024, 1, 1), date(2024, 12, 31))

        # 정정공시 시나리오: 수량 변경
        second = BuybackEvent(
            stock_code="035420", rcept_no="20240930000001",
            event_type="ACQUISITION", resolution_date=date(2024, 9, 27),
            planned_shares=200, planned_amount=2_000_000,
            period_start=None, period_end=None, purpose="이익소각(정정)",
        )
        _make_service(session, {"035420": [second]}).sync(date(2024, 1, 1), date(2024, 12, 31))

        rows = StockBuybackEventRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert len(rows) == 1
        assert rows[0].planned_shares == 200
        assert rows[0].purpose == "이익소각(정정)"
