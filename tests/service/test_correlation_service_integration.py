"""Integration test for CorrelationService.run — 세션 로드 + 세션 밖 계산."""

from datetime import date

import pytest

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import StockDailyCandle, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.service.correlation_service import CorrelationService


def _candle(ticker_id: int, d: date, close: float) -> StockDailyCandle:
    return StockDailyCandle(
        date=d, ticker_id=ticker_id,
        open=close, high=close, low=close, close=close, volume=1000, trade_value=None,
    )


def _seed(db: Database) -> None:
    """티커 2개(AAA, BBB) + 일봉 종가 시드. 수익률이 변동하도록 가격 구성."""
    with db.session_scope() as session:
        ticker_repo = TickerRepository(session)
        aaa = ticker_repo.save(Ticker(ticker="AAA", asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
        bbb = ticker_repo.save(Ticker(ticker="BBB", asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
        session.flush()
        prices = [100, 110, 104.5, 120, 114]  # 수익률 변동
        candle_repo = StockDailyCandleRepository(session)
        rows = []
        for i, p in enumerate(prices):
            d = date(2024, 1, 2 + i)
            rows.append(_candle(aaa.id, d, p))
            rows.append(_candle(bbb.id, d, p * 2))  # BBB = 2*AAA → 수익률 동일 → corr +1
        candle_repo.bulk_upsert(rows)


class TestCorrelationServiceRun:
    def test_등록티커_상관계산(self, db: Database) -> None:
        _seed(db)
        svc = CorrelationService(db)

        out = svc.run(["AAA", "BBB"])

        assert out.tickers == ["AAA", "BBB"]
        assert out.matrix[0][1] == pytest.approx(1.0)  # 동일 수익률 → +1
        assert out.observations == 4  # 5가격 → 4수익률
        assert out.dropped == []

    def test_미등록_티커는_dropped(self, db: Database) -> None:
        _seed(db)
        svc = CorrelationService(db)

        out = svc.run(["AAA", "BBB", "ZZZ"])

        assert "ZZZ" in out.dropped
        assert out.tickers == ["AAA", "BBB"]

    def test_날짜범위_필터(self, db: Database) -> None:
        _seed(db)
        svc = CorrelationService(db)

        out = svc.run(["AAA", "BBB"], start=date(2024, 1, 3), end=date(2024, 1, 5))

        assert out.period_start is not None
        assert out.period_start >= date(2024, 1, 3)
        assert out.period_end <= date(2024, 1, 5)

    def test_미지원_asset_예외(self, db: Database) -> None:
        svc = CorrelationService(db)
        with pytest.raises(ValueError, match="asset"):
            svc.run(["AAA", "BBB"], asset="crypto")
