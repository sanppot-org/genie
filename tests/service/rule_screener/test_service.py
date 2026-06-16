"""RuleScreeningService 통합 테스트 (SQLite in-memory, 실제 리포지토리)."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import (
    StockFinancialRatio,
    StockFundamental,
    StockIncomeStatement,
    Ticker,
)
from src.database.stock_buyback_event_repository import StockBuybackEventRepository
from src.database.stock_cancellation_event_repository import StockCancellationEventRepository
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.stock_financial_ratio_repository import StockFinancialRatioRepository
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.database.stock_treasury_stock_repository import StockTreasuryStockRepository
from src.database.ticker_repository import TickerRepository
from src.service.dividend_service import DividendService
from src.service.rule_screener.conditions import Comparator, Condition, Predicate
from src.service.rule_screener.service import RuleScreeningService
from src.service.screening_service import ScreeningService


def _build_service(session: Session) -> RuleScreeningService:
    ticker_repo = TickerRepository(session)
    fund_repo = StockFundamentalRepository(session)
    income_repo = StockIncomeStatementRepository(session)
    ratio_repo = StockFinancialRatioRepository(session)
    target_date = date(2026, 5, 15)

    # A: 영업이익 5년 연속 흑자 + EPS 5년 우상향 + PER 12
    ta = ticker_repo.save(Ticker(ticker="A00001", name="우량주",
                                 asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
    fund_repo.bulk_upsert([StockFundamental(ticker_id=ta.id, date=target_date, per=12.0, pbr=1.0, div=3.0)])
    income_repo.bulk_upsert([
        StockIncomeStatement(ticker_id=ta.id, period_type="ANNUAL", stac_yymm=f"{y}12", bsop_prti=100 + (y - 2020) * 10)
        for y in range(2020, 2025)
    ])
    ratio_repo.bulk_upsert([
        StockFinancialRatio(ticker_id=ta.id, stac_yymm=f"{y}12", eps=500 + (y - 2020) * 100)
        for y in range(2020, 2025)
    ])

    # B: 영업이익 5년중 3년만 흑자 (2년 적자) → count(min4) 탈락
    tb = ticker_repo.save(Ticker(ticker="B00002", name="변동주",
                                 asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
    fund_repo.bulk_upsert([StockFundamental(ticker_id=tb.id, date=target_date, per=8.0, pbr=0.5, div=5.0)])
    income_repo.bulk_upsert([
        StockIncomeStatement(ticker_id=tb.id, period_type="ANNUAL", stac_yymm="202012", bsop_prti=-10),
        StockIncomeStatement(ticker_id=tb.id, period_type="ANNUAL", stac_yymm="202112", bsop_prti=-5),
        StockIncomeStatement(ticker_id=tb.id, period_type="ANNUAL", stac_yymm="202212", bsop_prti=20),
        StockIncomeStatement(ticker_id=tb.id, period_type="ANNUAL", stac_yymm="202312", bsop_prti=30),
        StockIncomeStatement(ticker_id=tb.id, period_type="ANNUAL", stac_yymm="202412", bsop_prti=40),
    ])

    # C: 손익 데이터 2년치뿐 → window=5 조건에서 데이터부족 탈락
    tc = ticker_repo.save(Ticker(ticker="C00003", name="신규상장",
                                 asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
    fund_repo.bulk_upsert([StockFundamental(ticker_id=tc.id, date=target_date, per=9.0, pbr=0.7, div=4.0)])
    income_repo.bulk_upsert([
        StockIncomeStatement(ticker_id=tc.id, period_type="ANNUAL", stac_yymm="202312", bsop_prti=10),
        StockIncomeStatement(ticker_id=tc.id, period_type="ANNUAL", stac_yymm="202412", bsop_prti=20),
    ])

    # ScreeningService는 total_score 지표 공유용 (모든 자사주/배당 repo 필요).
    screening = ScreeningService(
        ticker_repository=ticker_repo,
        fundamental_repository=fund_repo,
        dividend_service=DividendService(StockDividendRepository(session), ticker_repo,
                                         StockDailyCandleRepository(session)),
        buyback_event_repository=StockBuybackEventRepository(session),
        cancellation_event_repository=StockCancellationEventRepository(session),
        treasury_stock_repository=StockTreasuryStockRepository(session),
        financial_ratio_repository=ratio_repo,
    )
    return RuleScreeningService(
        ticker_repository=ticker_repo,
        fundamental_repository=fund_repo,
        income_statement_repository=income_repo,
        financial_ratio_repository=ratio_repo,
        screening_service=screening,
    )


def test_operating_profit_and_eps_cagr_filter(session: Session) -> None:
    service = _build_service(session)
    conditions = [
        Condition(metric="bsop_prti", op="count", window=5,
                  predicate=Predicate(Comparator.GT, 0.0), min_count=4),  # 5년중 4년 흑자
        Condition(metric="eps", op="cagr", window=5, cmp=Comparator.GT, value=0.0),  # EPS 5년 CAGR>0
    ]
    result = service.screen(conditions=conditions, sort_by="total_score", order="desc",
                            limit=50, offset=0, today=date(2026, 5, 18))

    # A만 통과 (B는 흑자 3년 탈락, C는 데이터부족 탈락)
    assert result.total == 1
    assert result.rows[0].ticker == "A00001"
    assert result.rows[0].metrics["bsop_prti"] == {"count": 5.0, "window": 5}
    assert result.rows[0].metrics["eps"]["cagr"] > 0


def test_scalar_only_filter_and_sort(session: Session) -> None:
    service = _build_service(session)
    conditions = [Condition(metric="per", op="cmp", cmp=Comparator.LT, value=10.0)]  # B(8), C(9) 통과, A(12) 탈락
    result = service.screen(conditions=conditions, sort_by="per", order="asc",
                            limit=50, offset=0, today=date(2026, 5, 18))

    assert {r.ticker for r in result.rows} == {"B00002", "C00003"}
    assert [r.ticker for r in result.rows] == ["B00002", "C00003"]  # per ASC: 8 < 9
    assert result.rows[0].metrics["per"] == 8.0


def test_invalid_sort_by_raises(session: Session) -> None:
    service = _build_service(session)
    with pytest.raises(ValueError, match="정렬"):
        service.screen(conditions=[Condition(metric="per", op="cmp", cmp=Comparator.LT, value=10.0)],
                       sort_by="bsop_prti", order="desc", limit=50, offset=0)  # 시계열은 정렬 불가


def test_total_score_sort_populates_score(session: Session) -> None:
    """sort_by=total_score → SCORE source 로드 → 점수가 코드별로 올바르게 매핑되는지 검증.

    score_kr_stocks(limit=10**9) 경로와 ticker코드↔ticker_id 매핑 회귀 방지.
    B(PER 8/PBR 0.5/배당 5%)가 A(PER 12)·C보다 점수가 높아 1위여야 한다.
    """
    service = _build_service(session)
    conditions = [Condition(metric="per", op="cmp", cmp=Comparator.LT, value=10.0)]  # B, C 통과
    result = service.screen(conditions=conditions, sort_by="total_score", order="desc",
                            limit=50, offset=0, today=date(2026, 5, 18))

    assert {r.ticker for r in result.rows} == {"B00002", "C00003"}
    assert all(r.total_score is not None for r in result.rows)  # SCORE 로드됨(None 아님)
    assert result.rows[0].ticker == "B00002"  # 최고점 → 코드별 매핑 정상
    assert result.rows[0].total_score >= result.rows[1].total_score  # DESC
