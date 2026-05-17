"""Tests for DailyCandleSyncService."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_daily_candle_client import (
    PykrxDailyCandleClient,
    PykrxDailyCandleSnapshot,
)
from src.providers.pykrx_fundamental_client import KrxClosedDayError
from src.service.daily_candle_sync_service import DailyCandleSyncService


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


def _make_service(session: Session, snapshots: list[PykrxDailyCandleSnapshot]) -> DailyCandleSyncService:
    client = MagicMock(spec=PykrxDailyCandleClient)
    client.fetch_by_date.return_value = snapshots
    return DailyCandleSyncService(
        client=client,
        ticker_repository=TickerRepository(session),
        daily_candle_repository=StockDailyCandleRepository(session),
    )


class TestDailyCandleSyncService:
    """DailyCandleSyncService 통합 테스트 (인메모리 SQLite + pykrx mock)."""

    def test_sync_inserts_kr_stock_and_classifies_skips(
            self, session: Session, kr_stock_tickers: dict[str, int],
    ) -> None:
        """KR_STOCK 매핑 1건 upsert, ETF/미동기화 1건 skipped_unmapped, 거래정지 1건 skipped_no_trade."""
        target = date(2024, 1, 2)
        snapshots = [
            # 정상 KR_STOCK
            PykrxDailyCandleSnapshot("005930", open=70000, high=71000, low=69500,
                                     close=70500, volume=12_345_678, trade_value=870_000_000_000),
            # KR_STOCK이지만 거래정지 (volume=0 + open=0) → skipped_no_trade
            PykrxDailyCandleSnapshot("000660", open=0, high=0, low=0, close=0,
                                     volume=0, trade_value=0),
            # ETF (KR_ETF) → 매핑 dict에 없음 → skipped_unmapped
            PykrxDailyCandleSnapshot("069500", open=40000, high=40500, low=39800,
                                     close=40200, volume=1_000_000, trade_value=None),
        ]
        service = _make_service(session, snapshots)

        result = service.sync(target)

        assert result.received == 3
        assert result.upserted == 1
        assert result.skipped_unmapped == 1
        assert result.skipped_no_trade == 1

        rows = StockDailyCandleRepository(session).find_by_date(target)
        assert len(rows) == 1
        assert rows[0].ticker_id == kr_stock_tickers["005930"]
        assert rows[0].close == 70500
        assert rows[0].volume == 12_345_678
        assert rows[0].trade_value == 870_000_000_000

    def test_sync_propagates_closed_day_error(self, session: Session) -> None:
        """휴장일 client 에러는 그대로 전파 (수동 API에서 가시화)."""
        client = MagicMock(spec=PykrxDailyCandleClient)
        client.fetch_by_date.side_effect = KrxClosedDayError("휴장일")
        service = DailyCandleSyncService(
            client=client,
            ticker_repository=TickerRepository(session),
            daily_candle_repository=StockDailyCandleRepository(session),
        )

        with pytest.raises(KrxClosedDayError):
            service.sync(date(2024, 1, 6))  # 토요일

    def test_sync_is_idempotent_via_upsert(
            self, session: Session, kr_stock_tickers: dict[str, int],
    ) -> None:
        """같은 date 두 번 호출해도 row 수 변동 없고 값만 덮어쓰기."""
        target = date(2024, 1, 2)
        first = [
            PykrxDailyCandleSnapshot("005930", open=70000, high=71000, low=69500,
                                     close=70500, volume=12_000_000, trade_value=None),
        ]
        _make_service(session, first).sync(target)

        second = [
            PykrxDailyCandleSnapshot("005930", open=72000, high=73000, low=71500,
                                     close=72800, volume=15_000_000, trade_value=1_000_000_000_000),
        ]
        _make_service(session, second).sync(target)

        rows = StockDailyCandleRepository(session).find_by_date(target)
        assert len(rows) == 1
        assert rows[0].close == 72800
        assert rows[0].volume == 15_000_000
        assert rows[0].trade_value == 1_000_000_000_000
