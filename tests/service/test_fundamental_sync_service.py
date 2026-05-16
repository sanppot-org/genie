"""Tests for FundamentalSyncService."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockFundamental, Ticker
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_fundamental_client import (
    PykrxFundamentalClient,
    PykrxFundamentalSnapshot,
)
from src.service.fundamental_sync_service import FundamentalSyncService


@pytest.fixture
def kr_stock_tickers(session: Session) -> dict[str, int]:
    """KR_STOCK 2개 + KR_ETF 1개를 시드. {ticker: id} 반환."""
    repo = TickerRepository(session)
    samsung = repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    sk = repo.save(Ticker(
        ticker="000660", name="SK하이닉스",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    repo.save(Ticker(
        ticker="069500", name="KODEX 200",
        asset_type=AssetType.KR_ETF, data_source=DataSource.PYKRX.value,
    ))
    return {"005930": samsung.id, "000660": sk.id}


def _make_service(session: Session, snapshots: list[PykrxFundamentalSnapshot]) -> FundamentalSyncService:
    client = MagicMock(spec=PykrxFundamentalClient)
    client.fetch_by_date.return_value = snapshots
    return FundamentalSyncService(
        client=client,
        ticker_repository=TickerRepository(session),
        fundamental_repository=StockFundamentalRepository(session),
    )


class TestFundamentalSyncService:
    """FundamentalSyncService 통합 테스트 (인메모리 SQLite + pykrx mock)."""

    def test_sync_inserts_kr_stock_and_skips_etf(
            self, session: Session, kr_stock_tickers: dict[str, int],
    ) -> None:
        """KR_STOCK 2건은 upsert, ETF 1건은 skipped_unmapped."""
        target = date(2024, 1, 2)
        snapshots = [
            PykrxFundamentalSnapshot("005930", bps=50000, per=12.5, pbr=1.4, eps=4000, div=2.5, dps=1250),
            PykrxFundamentalSnapshot("000660", bps=80000, per=8.0, pbr=1.1, eps=10000, div=1.5, dps=1200),
            PykrxFundamentalSnapshot("069500", bps=None, per=None, pbr=None, eps=None, div=None, dps=None),
        ]
        service = _make_service(session, snapshots)

        result = service.sync(target)

        assert result.received == 3
        assert result.upserted == 2
        assert result.skipped_unmapped == 1

        rows = StockFundamentalRepository(session).find_by_date(target)
        assert {r.ticker_id for r in rows} == set(kr_stock_tickers.values())

    def test_sync_skips_unmapped_pykrx_codes(
            self, session: Session, kr_stock_tickers: dict[str, int],
    ) -> None:
        """pykrx 응답에 DB tickers 미동기화 코드(신규상장)가 있으면 skip."""
        snapshots = [
            PykrxFundamentalSnapshot("005930", bps=50000, per=12.5, pbr=1.4, eps=4000, div=2.5, dps=1250),
            PykrxFundamentalSnapshot("999998", bps=10000, per=5.0, pbr=0.5, eps=2000, div=0.0, dps=0.0),
        ]
        service = _make_service(session, snapshots)

        result = service.sync(date(2024, 1, 2))

        assert result.upserted == 1
        assert result.skipped_unmapped == 1

    def test_sync_is_idempotent_via_upsert(
            self, session: Session, kr_stock_tickers: dict[str, int],
    ) -> None:
        """같은 date 두 번 호출해도 row 수 변동 없고 값만 덮어쓰기."""
        target = date(2024, 1, 2)
        first = [
            PykrxFundamentalSnapshot("005930", bps=50000, per=12.5, pbr=1.4, eps=4000, div=2.5, dps=1250),
        ]
        _make_service(session, first).sync(target)

        second = [
            PykrxFundamentalSnapshot("005930", bps=60000, per=15.0, pbr=1.6, eps=4200, div=2.8, dps=1300),
        ]
        _make_service(session, second).sync(target)

        repo = StockFundamentalRepository(session)
        rows = repo.find_by_date(target)
        assert len(rows) == 1
        row: StockFundamental = rows[0]
        assert row.bps == 60000
        assert row.per == 15.0
        assert row.pbr == 1.6
