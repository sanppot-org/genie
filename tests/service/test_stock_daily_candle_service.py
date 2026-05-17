"""Tests for StockDailyCandleService (read)."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDailyCandle, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.service.exceptions import GenieError
from src.service.stock_daily_candle_service import StockDailyCandleService


@pytest.fixture
def samsung(session: Session) -> Ticker:
    """KR_STOCK 1개 시드 + 일봉 2건."""
    repo = TickerRepository(session)
    t = repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    candle_repo = StockDailyCandleRepository(session)
    candle_repo.bulk_upsert([
        StockDailyCandle(ticker_id=t.id, date=date(2024, 1, 2), open=70000, high=71000,
                          low=69500, close=70500, volume=12_000_000, trade_value=850_000_000_000),
        StockDailyCandle(ticker_id=t.id, date=date(2024, 1, 3), open=70500, high=72000,
                          low=70000, close=71800, volume=15_000_000, trade_value=None),
    ])
    return t


class TestStockDailyCandleService:
    """인메모리 SQLite 통합 테스트."""

    def test_정상_시계열_반환(self, session: Session, samsung: Ticker) -> None:
        service = StockDailyCandleService(
            ticker_repository=TickerRepository(session),
            daily_candle_repository=StockDailyCandleRepository(session),
        )

        ticker, rows = service.get_time_series("005930", None, None)

        assert ticker.ticker == "005930"
        assert ticker.name == "삼성전자"
        assert [r.date for r in rows] == [date(2024, 1, 2), date(2024, 1, 3)]
        assert rows[0].close == 70500
        assert rows[1].trade_value is None

    def test_기간_필터(self, session: Session, samsung: Ticker) -> None:
        service = StockDailyCandleService(
            ticker_repository=TickerRepository(session),
            daily_candle_repository=StockDailyCandleRepository(session),
        )

        _, rows = service.get_time_series("005930", date(2024, 1, 3), None)

        assert [r.date for r in rows] == [date(2024, 1, 3)]

    def test_미발견_ticker_404(self, session: Session) -> None:
        service = StockDailyCandleService(
            ticker_repository=TickerRepository(session),
            daily_candle_repository=StockDailyCandleRepository(session),
        )

        with pytest.raises(GenieError):
            service.get_time_series("999999", None, None)
