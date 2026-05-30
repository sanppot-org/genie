"""Tests for CancellationSyncService (인메모리 sqlite + mock DART client)."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import Ticker
from src.database.stock_cancellation_event_repository import StockCancellationEventRepository
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import CancellationEvent, DartCompanyClient
from src.service.cancellation_sync_service import CancellationSyncService


@pytest.fixture
def kr_stock_ticker_id(db: Database) -> int:
    """삼성전자 KR_STOCK 1개 적재 후 ticker_id 반환 (세션 분리 안전)."""
    with db.session_scope() as session:
        ticker = TickerRepository(session).save(Ticker(
            ticker="005930", name="삼성전자",
            asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
        ))
        session.flush()
        ticker_id = ticker.id
    assert ticker_id is not None
    return ticker_id


def _make_service(
        db: Database,
        responses: dict[str, list[CancellationEvent] | Exception],
) -> CancellationSyncService:
    client = MagicMock(spec=DartCompanyClient)

    def fake_fetch(stock_code: str, from_date: date, to_date: date) -> list[CancellationEvent]:
        res = responses.get(stock_code, [])
        if isinstance(res, Exception):
            raise res
        return res

    client.fetch_cancellation_events.side_effect = fake_fetch
    return CancellationSyncService(database=db, dart_client=client, chunk_size=200, throttle_sec=0)


def _event(rcept_no: str, common: int) -> CancellationEvent:
    return CancellationEvent(
        stock_code="005930", rcept_no=rcept_no, report_nm="주식소각결정",
        resolution_date=date(2025, 2, 18), cancel_date=date(2025, 2, 20),
        common_shares=common, preferred_shares=6_912_036,
        cancel_amount=3_048_696_999_300, acquisition_method="기취득 자기주식",
    )


def test_sync_upserts_and_is_idempotent(db: Database, kr_stock_ticker_id: int) -> None:
    """소각 이벤트 적재 + 동일 rcept_no 재호출은 row 1개 유지(최신값 덮어쓰기)."""
    service = _make_service(db, {"005930": [_event("20250218800029", common=50_144_628)]})
    result = service.sync(date(2025, 1, 1), date(2025, 12, 31))

    assert result.ticker_count == 1
    assert result.rows_received == 1
    assert result.rows_upserted == 1
    assert result.api_calls_failed == 0

    # 정정공시 시나리오: 수량 변경 후 재호출
    _make_service(db, {"005930": [_event("20250218800029", common=99_999_999)]}).sync(
        date(2025, 1, 1), date(2025, 12, 31)
    )

    with db.session_scope() as session:
        rows = StockCancellationEventRepository(session).find_by_ticker(kr_stock_ticker_id)
        assert len(rows) == 1
        assert rows[0].common_shares == 99_999_999
        assert rows[0].cancel_amount == 3_048_696_999_300


def test_sync_best_effort_on_exception(db: Database, kr_stock_ticker_id: int) -> None:
    """종목별 DART 예외는 api_calls_failed로 카운트하고 진행(skip)."""
    service = _make_service(db, {"005930": RuntimeError("boom")})
    result = service.sync(date(2025, 1, 1), date(2025, 12, 31))

    assert result.api_calls_attempted == 1
    assert result.api_calls_failed == 1
    assert result.rows_upserted == 0
