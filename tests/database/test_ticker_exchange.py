"""Ticker.exchange 컬럼 테스트 (인메모리 SQLite, 모델 기반 create_all)."""

from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository


def test_ticker_persists_exchange(session: Session) -> None:
    repo = TickerRepository(session)
    saved = repo.save(Ticker(
        ticker="AAPL", name="Apple Inc",
        asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value,
        exchange="NAS",
    ))
    assert saved.exchange == "NAS"
    # KR 종목은 NULL 허용
    kr = repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    assert kr.exchange is None
