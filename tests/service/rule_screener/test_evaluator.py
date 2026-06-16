"""평가기 단위 테스트 — extract_metric + evaluate_ticker (DB 없이 row 더미 사용)."""

import datetime

from src.database.models import StockFinancialRatio, StockFundamental, StockIncomeStatement
from src.service.rule_screener.conditions import Comparator, Condition, Predicate
from src.service.rule_screener.evaluator import TickerMetrics, evaluate_ticker, extract_metric


def _tm() -> TickerMetrics:
    return TickerMetrics(
        fundamental=StockFundamental(ticker_id=1, date=datetime.date(2024, 12, 31), per=12.0, pbr=0.8, div=3.0, eps=500, bps=4000, dps=30),
        income_annual=[  # 최신순 (loader가 DESC로 줌)
            StockIncomeStatement(ticker_id=1, period_type="ANNUAL", stac_yymm="202412", bsop_prti=200),
            StockIncomeStatement(ticker_id=1, period_type="ANNUAL", stac_yymm="202312", bsop_prti=100),
            StockIncomeStatement(ticker_id=1, period_type="ANNUAL", stac_yymm="202212", bsop_prti=-50),
        ],
        ratio_annual=[
            StockFinancialRatio(ticker_id=1, stac_yymm="202412", eps=600),
            StockFinancialRatio(ticker_id=1, stac_yymm="202312", eps=300),
        ],
        total_score=42.0,
    )


def test_extract_scalar_and_series() -> None:
    tm = _tm()
    assert extract_metric("per", tm) == 12.0          # 스냅샷 스칼라
    assert extract_metric("total_score", tm) == 42.0  # 계산값 스칼라
    assert extract_metric("bsop_prti", tm) == [200.0, 100.0, -50.0]  # 시계열 최신순
    assert extract_metric("eps", tm) == [600.0, 300.0]


def test_extract_keeps_none_position_in_series() -> None:
    tm = _tm()
    tm.income_annual[1].bsop_prti = None  # 중간 연도 결측 → None으로 위치 보존
    assert extract_metric("bsop_prti", tm) == [200.0, None, -50.0]


def test_evaluate_passes_when_all_conditions_met() -> None:
    tm = _tm()
    conditions = [
        Condition(metric="bsop_prti", op="count", window=3,
                  predicate=Predicate(Comparator.GT, 0.0), min_count=2),  # 3년중 2 흑자 → 2 통과
        Condition(metric="per", op="cmp", cmp=Comparator.LT, value=15.0),  # 12<15 통과
    ]
    res = evaluate_ticker(tm, conditions)
    assert res.passed is True
    assert res.insufficient is False
    assert res.metrics["per"] == 12.0
    assert res.metrics["bsop_prti"] == {"count": 2.0, "window": 3}


def test_evaluate_fails_short_circuits() -> None:
    tm = _tm()
    conditions = [Condition(metric="per", op="cmp", cmp=Comparator.LT, value=10.0)]  # 12<10 실패
    res = evaluate_ticker(tm, conditions)
    assert res.passed is False


def test_evaluate_insufficient_excludes() -> None:
    tm = _tm()
    conditions = [Condition(metric="eps", op="cagr", window=5, cmp=Comparator.GT, value=0.0)]  # 2년치뿐
    res = evaluate_ticker(tm, conditions)
    assert res.passed is False
    assert res.insufficient is True
