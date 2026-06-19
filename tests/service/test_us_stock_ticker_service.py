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
    """NASDAQ/NYSE/AMEX + ETF/US 별 StockListing 반환 mock.

    NVDA는 주식목록과 ETF/US 양쪽에 두어 충돌 우선순위(주식 우선)를 검증한다.
    """
    mapping = {
        "NASDAQ": _listing([("AAPL", "Apple Inc"), ("NVDA", "NVIDIA Corp")]),
        "NYSE": _listing([("LLY", "Eli Lilly and Co")]),
        "AMEX": _listing([("IMO", "Imperial Oil Ltd")]),
        "ETF/US": _listing([("TQQQ", "ProShares UltraPro QQQ"), ("NVDA", "Bogus NVDA ETF")]),
    }
    return patch(
        "src.service.us_stock_ticker_service.fdr.StockListing",
        side_effect=lambda mkt: mapping[mkt],
    )


def _patched_listing_custom(etf_side_effect: object):
    """주식목록(NASDAQ/NYSE/AMEX)은 정상, ETF/US만 커스텀 동작(예외/잘못된 컬럼) 주입.

    etf_side_effect가 Exception이면 raise하고, 그 외(DataFrame 등)는 그대로 반환한다.
    """
    stock_mapping = {
        "NASDAQ": _listing([("AAPL", "Apple Inc")]),
        "NYSE": _listing([("LLY", "Eli Lilly and Co")]),
        "AMEX": _listing([("IMO", "Imperial Oil Ltd")]),
    }

    def _side_effect(mkt: str) -> pd.DataFrame:
        if mkt == "ETF/US":
            if isinstance(etf_side_effect, Exception):
                raise etf_side_effect
            return etf_side_effect  # type: ignore[return-value]
        return stock_mapping[mkt]

    return patch(
        "src.service.us_stock_ticker_service.fdr.StockListing",
        side_effect=_side_effect,
    )


def test_register_continues_when_etf_listing_raises(db: Database, session: Session) -> None:
    """ETF/US 로드가 예외를 던져도 주식 심볼은 정상 US_STOCK/NAS로 등록된다 (ETF 보강만 skip)."""
    service = UsStockTickerService(database=db)
    with _patched_listing_custom(RuntimeError("ETF/US fetch failed")):
        result = service.register(["AAPL"])

    assert result.registered == 1
    aapl = TickerRepository(session).find_by_ticker("AAPL")
    assert aapl is not None
    assert aapl.asset_type == AssetType.US_STOCK
    assert aapl.exchange == "NAS"
    assert aapl.data_source == DataSource.FDR.value


def test_register_continues_when_etf_listing_columns_missing(db: Database, session: Session) -> None:
    """ETF/US가 잘못된 컬럼을 반환하면 ETF 보강은 skip되고 주식 등록은 지속된다."""
    bad_etf_df = pd.DataFrame({"Ticker": ["TQQQ"]})  # 'Symbol'/'Name' 누락
    service = UsStockTickerService(database=db)
    with _patched_listing_custom(bad_etf_df):
        result = service.register(["AAPL", "TQQQ"])

    # 주식 등록은 계속
    assert result.registered == 1
    aapl = TickerRepository(session).find_by_ticker("AAPL")
    assert aapl is not None
    assert aapl.asset_type == AssetType.US_STOCK
    assert aapl.exchange == "NAS"

    # ETF 보강이 skip돼 ETF 전용 심볼은 unknown 처리
    assert result.skipped_unknown == 1
    assert "TQQQ" in result.skipped
    assert TickerRepository(session).find_by_ticker("TQQQ") is None


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


def test_register_rehomes_ticker_with_different_source_and_type(db: Database, session: Session) -> None:
    """다른 data_source/asset_type으로 등록된 ticker를 US_STOCK/FDR로 재분류한다."""
    from src.database.models import Ticker

    # 같은 심볼 AAPL을 KR_STOCK/PYKRX로 미리 저장
    repo = TickerRepository(session)
    repo.save(Ticker(
        ticker="AAPL",
        name="Old Name",
        asset_type=AssetType.KR_STOCK,
        data_source=DataSource.PYKRX.value,
        exchange="KRX",
    ))
    session.commit()

    service = UsStockTickerService(database=db)
    with _patched_listing():
        result = service.register(["AAPL"])

    assert result.updated == 1
    assert result.registered == 0

    session.expire_all()
    aapl = TickerRepository(session).find_by_ticker("AAPL")
    assert aapl is not None
    assert aapl.asset_type == AssetType.US_STOCK
    assert aapl.data_source == DataSource.FDR.value
    assert aapl.exchange == "NAS"


def test_register_etf_symbol_uses_us_etf_type(db: Database, session: Session) -> None:
    """ETF/US에만 있는 심볼은 US_ETF(exchange=None)/FDR로 등록된다."""
    service = UsStockTickerService(database=db)
    with _patched_listing():
        result = service.register(["TQQQ"])

    assert result.registered == 1
    tqqq = TickerRepository(session).find_by_ticker("TQQQ")
    assert tqqq is not None
    assert tqqq.asset_type == AssetType.US_ETF
    assert tqqq.exchange is None
    assert tqqq.data_source == DataSource.FDR.value


def test_register_etf_is_idempotent_and_keeps_us_etf(db: Database, session: Session) -> None:
    """같은 ETF를 두 번 register해도 US_ETF 유지 (US_STOCK으로 안 바뀜) — 핵심 회귀 가드."""
    service = UsStockTickerService(database=db)
    with _patched_listing():
        service.register(["TQQQ"])
        result = service.register(["TQQQ"])

    assert result.updated == 1
    session.expire_all()
    tqqq = TickerRepository(session).find_by_ticker("TQQQ")
    assert tqqq is not None
    assert tqqq.asset_type == AssetType.US_ETF
    assert tqqq.exchange is None


def test_register_stock_wins_over_etf_on_conflict(db: Database, session: Session) -> None:
    """주식목록과 ETF/US 양쪽에 있는 심볼은 주식(US_STOCK) 우선으로 등록된다."""
    service = UsStockTickerService(database=db)
    with _patched_listing():
        result = service.register(["NVDA"])

    assert result.registered == 1
    nvda = TickerRepository(session).find_by_ticker("NVDA")
    assert nvda is not None
    assert nvda.asset_type == AssetType.US_STOCK
    assert nvda.exchange == "NAS"
    assert nvda.name == "NVIDIA Corp"
