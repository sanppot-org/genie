"""Tests for TreasuryStockSyncService (인메모리 sqlite + mock DART client)."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import Ticker
from src.database.stock_treasury_stock_repository import StockTreasuryStockRepository
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import DartCompanyClient, TreasuryStockStatus
from src.service.treasury_stock_sync_service import (
    TreasuryStockSyncService,
    _latest_reprt_period,
)


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
        responses: dict[str, TreasuryStockStatus | None | Exception],
) -> TreasuryStockSyncService:
    client = MagicMock(spec=DartCompanyClient)

    def fake_fetch(stock_code: str, bsns_year: int, reprt_code: str) -> TreasuryStockStatus | None:
        res = responses.get(stock_code)
        if isinstance(res, Exception):
            raise res
        return res

    client.fetch_treasury_stock_status.side_effect = fake_fetch
    return TreasuryStockSyncService(database=db, client=client)


class TestTreasuryStockSyncService:
    def test_sync_period_upserts_ratio(self, db: Database, kr_stock_ticker_id: int) -> None:
        """정상 응답 → treasury_ratio 계산 + 적재."""
        responses = {
            "005930": TreasuryStockStatus(
                stock_code="005930",
                stlm_dt=date(2024, 12, 31),
                reprt_code="11011",
                issued_shares=6_792_669_250,
                treasury_shares=33_750_000,
                rcept_no="20250311001085",
            ),
        }
        result = _make_service(db, responses).sync_period(2024, "11011")

        assert result.tickers == 1
        assert result.upserted == 1
        assert result.skipped_no_data == 0
        assert result.skipped_failure == 0

        with db.session_scope() as session:
            rows = StockTreasuryStockRepository(session).find_by_ticker(kr_stock_ticker_id)
            assert len(rows) == 1
            assert rows[0].stlm_dt == date(2024, 12, 31)
            assert rows[0].issued_shares == 6_792_669_250
            assert rows[0].treasury_shares == 33_750_000
            assert rows[0].treasury_ratio == pytest.approx(0.4969, abs=1e-3)
            assert rows[0].reprt_code == "11011"
            assert rows[0].rcept_no == "20250311001085"

    def test_sync_period_counts_no_data(self, db: Database, kr_stock_ticker_id: int) -> None:
        """DART 응답 없음(None)은 skipped_no_data로 카운트."""
        result = _make_service(db, {"005930": None}).sync_period(2024, "11013")

        assert result.upserted == 0
        assert result.skipped_no_data == 1
        assert result.skipped_failure == 0

    def test_sync_period_counts_failure(self, db: Database, kr_stock_ticker_id: int) -> None:
        """클라이언트 예외는 skipped_failure로 카운트 (sync 전체는 진행)."""
        result = _make_service(db, {"005930": RuntimeError("boom")}).sync_period(2024, "11011")

        assert result.upserted == 0
        assert result.skipped_no_data == 0
        assert result.skipped_failure == 1

    def test_sync_period_is_idempotent(self, db: Database, kr_stock_ticker_id: int) -> None:
        """같은 (ticker_id, stlm_dt) 재호출 시 row는 1개로 유지되고 최신 값으로 덮어쓰기."""
        first = TreasuryStockStatus(
            stock_code="005930", stlm_dt=date(2024, 12, 31), reprt_code="11011",
            issued_shares=1_000_000, treasury_shares=10_000, rcept_no="A",
        )
        _make_service(db, {"005930": first}).sync_period(2024, "11011")

        # 같은 결산일이지만 자사주 늘어남 (분기 보고서 정정 시나리오)
        second = TreasuryStockStatus(
            stock_code="005930", stlm_dt=date(2024, 12, 31), reprt_code="11011",
            issued_shares=1_000_000, treasury_shares=20_000, rcept_no="B",
        )
        _make_service(db, {"005930": second}).sync_period(2024, "11011")

        with db.session_scope() as session:
            rows = StockTreasuryStockRepository(session).find_by_ticker(kr_stock_ticker_id)
            assert len(rows) == 1
            assert rows[0].treasury_shares == 20_000
            assert rows[0].treasury_ratio == pytest.approx(2.0)
            assert rows[0].rcept_no == "B"

    def test_sync_period_accepts_zero_treasury_shares(self, db: Database, kr_stock_ticker_id: int) -> None:
        """자사주 0 종목도 정상 적재 (점수표 5점 의미 있는 값)."""
        responses = {
            "005930": TreasuryStockStatus(
                stock_code="005930", stlm_dt=date(2024, 12, 31), reprt_code="11011",
                issued_shares=1_000_000, treasury_shares=0, rcept_no="X",
            ),
        }
        result = _make_service(db, responses).sync_period(2024, "11011")

        assert result.upserted == 1
        with db.session_scope() as session:
            rows = StockTreasuryStockRepository(session).find_by_ticker(kr_stock_ticker_id)
            assert rows[0].treasury_shares == 0
            assert rows[0].treasury_ratio == pytest.approx(0.0)


class TestLatestReprtPeriod:
    @pytest.mark.parametrize(("today", "expected"), [
        # 4/8 ~ 5/21: 전년 사업보고서
        (date(2026, 4, 8), (2025, "11011")),
        (date(2026, 5, 21), (2025, "11011")),
        # 5/22 ~ 8/21: 당년 1분기
        (date(2026, 5, 22), (2026, "11013")),
        (date(2026, 8, 21), (2026, "11013")),
        # 8/22 ~ 11/21: 당년 반기
        (date(2026, 8, 22), (2026, "11012")),
        (date(2026, 11, 21), (2026, "11012")),
        # 11/22 ~ 다음해 4/7: 당년 3분기
        (date(2026, 11, 22), (2026, "11014")),
        (date(2026, 12, 31), (2026, "11014")),
        (date(2027, 1, 5), (2026, "11014")),
        (date(2027, 4, 7), (2026, "11014")),
    ])
    def test_period_boundaries(self, today: date, expected: tuple[int, str]) -> None:
        assert _latest_reprt_period(today) == expected
