"""UsStockTickerService 테스트 (StockListing mock)."""

from unittest.mock import patch

import pandas as pd
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.ticker_repository import TickerRepository
from src.service.us_stock_ticker_service import UsStockTickerService


def _listing(symbols_names: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Symbol": [s for s, _ in symbols_names], "Name": [n for _, n in symbols_names]}
    )


def _patched_listing():
    """NASDAQ/NYSE/AMEX 별 StockListing 반환 mock."""
    mapping = {
        "NASDAQ": _listing([("AAPL", "Apple Inc"), ("NVDA", "NVIDIA Corp")]),
        "NYSE": _listing([("LLY", "Eli Lilly and Co")]),
        "AMEX": _listing([("IMO", "Imperial Oil Ltd")]),
    }
    return patch(
        "src.service.us_stock_ticker_service.fdr.StockListing",
        side_effect=lambda mkt: mapping[mkt],
    )


def test_register_enriches_name_and_exchange(db: Database, session: Session) -> None:
    service = UsStockTickerService(database=db)
    with _patched_listing():
        result = service.register(["AAPL", "LLY", "ZZZZ"])

    assert result.registered == 2
    assert result.skipped_unknown == 1
    assert "ZZZZ" in result.skipped

    repo = TickerRepository(session)
    aapl = repo.find_by_ticker("AAPL")
    assert aapl.name == "Apple Inc"
    assert aapl.exchange == "NAS"
    assert aapl.asset_type == AssetType.US_STOCK
    assert aapl.data_source == DataSource.FDR.value
    assert repo.find_by_ticker("LLY").exchange == "NYS"


def test_register_is_idempotent(db: Database, session: Session) -> None:
    service = UsStockTickerService(database=db)
    with _patched_listing():
        service.register(["AAPL"])
        result = service.register(["AAPL"])  # 두 번째 호출
    assert result.updated == 1
    assert len(TickerRepository(session).find_by_data_source(DataSource.FDR)) == 1
