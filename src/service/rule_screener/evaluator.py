"""종목별 지표 추출 + 조건 AND 평가."""

from dataclasses import dataclass, field

from src.database.models import StockFinancialRatio, StockFundamental, StockIncomeStatement
from src.service.rule_screener.conditions import Condition
from src.service.rule_screener.metrics import METRIC_REGISTRY, MetricSource
from src.service.rule_screener.operators import (
    OpResult,
    eval_avg,
    eval_cagr,
    eval_cmp,
    eval_count,
    eval_streak,
)

# 응답용 표시값: 스칼라(cmp) 또는 {count/cagr/streak/avg: 값} 작은 dict.
MetricDisplay = float | dict[str, float | int | None] | None
# 지표 추출 결과: 스칼라 또는 시계열(최신순, NULL 위치 보존).
MetricValue = float | None | list[float | None]


@dataclass
class TickerMetrics:
    """한 종목의 평가 입력 묶음 (loader가 채움)."""

    fundamental: StockFundamental | None
    income_annual: list[StockIncomeStatement]  # 최신순(DESC)
    ratio_annual: list[StockFinancialRatio]     # 최신순(DESC)
    total_score: float | None


@dataclass
class EvalResult:
    passed: bool
    insufficient: bool
    metrics: dict[str, MetricDisplay] = field(default_factory=dict)  # 표시용 계산값(참조 지표만)


def _scalar(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]


def _series(rows: list[StockIncomeStatement] | list[StockFinancialRatio], attr: str) -> list[float | None]:
    """최신순 시계열을 float|None 리스트로. NULL 연도는 None으로 위치 보존(연산자가 윈도우에서 판정)."""
    return [None if getattr(r, attr) is None else float(getattr(r, attr)) for r in rows]


def extract_metric(metric: str, tm: TickerMetrics) -> MetricValue:
    """metric 키 → 스칼라(float|None) 또는 시계열(list[float|None], 최신순, NULL 보존)."""
    spec = METRIC_REGISTRY[metric]
    if spec.source is MetricSource.FUNDAMENTAL:
        return None if tm.fundamental is None else _scalar(getattr(tm.fundamental, spec.attr))
    if spec.source is MetricSource.SCORE:
        return tm.total_score
    if spec.source is MetricSource.INCOME_ANNUAL:
        return _series(tm.income_annual, spec.attr)
    return _series(tm.ratio_annual, spec.attr)


def _run_operator(c: Condition, value: MetricValue) -> OpResult:
    if c.op == "cmp":
        assert c.cmp is not None and c.value is not None
        assert not isinstance(value, list)  # 스칼라 지표만 cmp 허용(검증 통과 가정)
        return eval_cmp(value, c.cmp, c.value)
    assert isinstance(value, list)  # 시계열 지표만 시계열 op 허용(검증 통과 가정)
    if c.op == "count":
        assert c.window is not None and c.predicate is not None and c.min_count is not None
        return eval_count(value, c.window, c.predicate, c.min_count)
    if c.op == "streak":
        assert c.window is not None and c.predicate is not None
        return eval_streak(value, c.window, c.predicate)
    if c.op == "cagr":
        assert c.window is not None and c.cmp is not None and c.value is not None
        return eval_cagr(value, c.window, c.cmp, c.value)
    # avg
    assert c.window is not None and c.cmp is not None and c.value is not None
    return eval_avg(value, c.window, c.cmp, c.value)


def _display(c: Condition, res: OpResult) -> MetricDisplay:
    """응답용 표시값. cmp→스칼라값, count→{count,window}, 그 외 시계열→{op:value}."""
    if c.op == "cmp":
        return res.value
    if c.op == "count":
        return {"count": res.value, "window": c.window}
    return {c.op: res.value}


def evaluate_ticker(tm: TickerMetrics, conditions: list[Condition]) -> EvalResult:
    """조건 전부(AND) 평가. 하나라도 데이터부족이면 insufficient, 하나라도 불만족이면 탈락.

    metrics는 metric 키로 표시값을 담는다. 같은 metric에 조건이 둘 이상이면 마지막 조건의
    표시값만 남는다(필터링 자체는 AND로 모두 적용됨). 스칼라 cmp 범위(per>5 AND per<15)는
    동일 값이라 무손실; 동일 시계열 metric에 서로 다른 op를 쓰는 드문 경우만 표시 손실 — Phase 1 수용.
    """
    metrics: dict[str, MetricDisplay] = {}
    for c in conditions:
        value = extract_metric(c.metric, tm)
        res = _run_operator(c, value)
        if res.insufficient:
            return EvalResult(passed=False, insufficient=True)
        if not res.passed:
            return EvalResult(passed=False, insufficient=False)
        metrics[c.metric] = _display(c, res)
    return EvalResult(passed=True, insufficient=False, metrics=metrics)
