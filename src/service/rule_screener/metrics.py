"""지표 vocabulary 정의 + 조건 유효성 검증.

연간 시계열 지표는 12월 결산(stac_yymm 끝 '12')만 사용 — loader가 필터링.
단위는 원본 그대로(손익계산서=억원, 재무비율 eps=원 등); 비교 value도 원본 단위.
"""

from dataclasses import dataclass
from enum import Enum

from src.service.rule_screener.conditions import Condition


class MetricSource(str, Enum):
    FUNDAMENTAL = "fundamental"      # 최신 스냅샷 스칼라 (stock_fundamentals)
    INCOME_ANNUAL = "income_annual"  # 손익계산서 연간 시계열 (억원)
    RATIO_ANNUAL = "ratio_annual"    # 재무비율 연간 시계열
    SCORE = "score"                  # 계산값 스칼라 (기존 65점)


@dataclass(frozen=True)
class MetricSpec:
    key: str
    source: MetricSource
    attr: str           # 소스 row의 속성명 (SCORE는 빈 문자열)
    is_timeseries: bool
    unit: str


METRIC_REGISTRY: dict[str, MetricSpec] = {
    # 스냅샷 (stock_fundamentals 최신일)
    "per": MetricSpec("per", MetricSource.FUNDAMENTAL, "per", False, "배수"),
    "pbr": MetricSpec("pbr", MetricSource.FUNDAMENTAL, "pbr", False, "배수"),
    "div": MetricSpec("div", MetricSource.FUNDAMENTAL, "div", False, "%"),
    "dps": MetricSpec("dps", MetricSource.FUNDAMENTAL, "dps", False, "원"),
    "eps_snapshot": MetricSpec("eps_snapshot", MetricSource.FUNDAMENTAL, "eps", False, "원"),
    "bps_snapshot": MetricSpec("bps_snapshot", MetricSource.FUNDAMENTAL, "bps", False, "원"),
    # 손익계산서 연간 (억원)
    "sale_account": MetricSpec("sale_account", MetricSource.INCOME_ANNUAL, "sale_account", True, "억원"),
    "bsop_prti": MetricSpec("bsop_prti", MetricSource.INCOME_ANNUAL, "bsop_prti", True, "억원"),
    "thtr_ntin": MetricSpec("thtr_ntin", MetricSource.INCOME_ANNUAL, "thtr_ntin", True, "억원"),
    "sale_totl_prfi": MetricSpec("sale_totl_prfi", MetricSource.INCOME_ANNUAL, "sale_totl_prfi", True, "억원"),
    "op_prfi": MetricSpec("op_prfi", MetricSource.INCOME_ANNUAL, "op_prfi", True, "억원"),
    # 재무비율 연간
    "eps": MetricSpec("eps", MetricSource.RATIO_ANNUAL, "eps", True, "원"),
    "bps": MetricSpec("bps", MetricSource.RATIO_ANNUAL, "bps", True, "원"),
    "sps": MetricSpec("sps", MetricSource.RATIO_ANNUAL, "sps", True, "원"),
    "roe": MetricSpec("roe", MetricSource.RATIO_ANNUAL, "roe", True, "%"),
    "debt_ratio": MetricSpec("debt_ratio", MetricSource.RATIO_ANNUAL, "debt_ratio", True, "%"),
    "reserve_rate": MetricSpec("reserve_rate", MetricSource.RATIO_ANNUAL, "reserve_rate", True, "%"),
    "revenue_growth": MetricSpec("revenue_growth", MetricSource.RATIO_ANNUAL, "revenue_growth", True, "%"),
    "op_growth": MetricSpec("op_growth", MetricSource.RATIO_ANNUAL, "op_growth", True, "%"),
    "net_growth": MetricSpec("net_growth", MetricSource.RATIO_ANNUAL, "net_growth", True, "%"),
    # 계산값
    "total_score": MetricSpec("total_score", MetricSource.SCORE, "", False, "점"),
}

# sort_by로 허용되는 스칼라 지표 (시계열 지표는 정렬 모호 → 제외).
SCALAR_SORT_KEYS: frozenset[str] = frozenset(
    key for key, spec in METRIC_REGISTRY.items() if not spec.is_timeseries
)

_TIMESERIES_OPS = {"count", "cagr", "streak", "avg"}
_SCALAR_OPS = {"cmp"}


def validate_condition(c: Condition) -> None:
    """조건 1개의 유효성 검증. 위반 시 ValueError(한국어 메시지)."""
    spec = METRIC_REGISTRY.get(c.metric)
    if spec is None:
        raise ValueError(f"알 수 없는 지표: {c.metric}")
    if c.op in _TIMESERIES_OPS and not spec.is_timeseries:
        raise ValueError(f"{c.metric}는 시계열 지표가 아니어서 '{c.op}' 연산을 쓸 수 없습니다")
    if c.op in _SCALAR_OPS and spec.is_timeseries:
        raise ValueError(f"{c.metric}는 시계열 지표여서 'cmp' 연산을 쓸 수 없습니다")

    if c.op == "cmp":
        if c.cmp is None or c.value is None:
            raise ValueError("cmp 연산은 cmp, value가 필요합니다")
    elif c.op == "count":
        if c.window is None or c.predicate is None or c.min_count is None:
            raise ValueError("count 연산은 window, predicate, min_count가 필요합니다")
        if c.window < 1:
            raise ValueError("count 연산의 window는 1 이상이어야 합니다")
        if not (1 <= c.min_count <= c.window):
            raise ValueError("count 연산의 min_count는 1 이상 window 이하여야 합니다")
    elif c.op == "streak":
        if c.window is None or c.predicate is None:
            raise ValueError("streak 연산은 window, predicate가 필요합니다")
        if c.window < 1:
            raise ValueError("streak 연산의 window는 1 이상이어야 합니다")
    elif c.op in ("cagr", "avg"):
        if c.window is None or c.cmp is None or c.value is None:
            raise ValueError(f"{c.op} 연산은 window, cmp, value가 필요합니다")
        if c.op == "cagr" and c.window < 2:
            raise ValueError("cagr 연산의 window는 2 이상이어야 합니다")
        if c.op == "avg" and c.window < 1:
            raise ValueError("avg 연산의 window는 1 이상이어야 합니다")
    else:
        raise ValueError(f"알 수 없는 연산: {c.op}")
