"""연간 시계열 bulk 조회 (스크리너용) 테스트."""

from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockFinancialRatio, StockIncomeStatement, Ticker
from src.database.stock_financial_ratio_repository import StockFinancialRatioRepository
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.database.ticker_repository import TickerRepository


def _ticker(session: Session, code: str) -> int:
    repo = TickerRepository(session)
    t = repo.save(Ticker(ticker=code, name=f"{code}_n",
                         asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
    return t.id


def test_income_annual_series_desc_and_only_december(session: Session) -> None:
    tid = _ticker(session, "A00001")
    repo = StockIncomeStatementRepository(session)
    repo.bulk_upsert([
        StockIncomeStatement(ticker_id=tid, period_type="ANNUAL", stac_yymm="202312", bsop_prti=100),
        StockIncomeStatement(ticker_id=tid, period_type="ANNUAL", stac_yymm="202412", bsop_prti=200),
        StockIncomeStatement(ticker_id=tid, period_type="ANNUAL", stac_yymm="202503", bsop_prti=999),  # 잠정(...03) 제외
        StockIncomeStatement(ticker_id=tid, period_type="QUARTER", stac_yymm="202412", bsop_prti=50),  # 분기 제외
    ])

    out = repo.find_annual_series_by_tickers([tid])

    assert [r.stac_yymm for r in out[tid]] == ["202412", "202312"]  # DESC, ...12만
    assert [r.bsop_prti for r in out[tid]] == [200, 100]


def test_income_empty_input_returns_empty(session: Session) -> None:
    repo = StockIncomeStatementRepository(session)
    assert repo.find_annual_series_by_tickers([]) == {}


def test_ratio_annual_series_desc_and_only_december(session: Session) -> None:
    tid = _ticker(session, "B00002")
    repo = StockFinancialRatioRepository(session)
    repo.bulk_upsert([
        StockFinancialRatio(ticker_id=tid, stac_yymm="202312", eps=1000),
        StockFinancialRatio(ticker_id=tid, stac_yymm="202412", eps=1200),
        StockFinancialRatio(ticker_id=tid, stac_yymm="202603", eps=9999),  # 잠정 제외
    ])

    out = repo.find_annual_series_by_tickers([tid])

    assert [r.stac_yymm for r in out[tid]] == ["202412", "202312"]
    assert [r.eps for r in out[tid]] == [1200, 1000]
