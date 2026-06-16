"""규칙 조건의 내부 표현 + 비교 연산."""

from dataclasses import dataclass
from enum import Enum


class Comparator(str, Enum):
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    EQ = "eq"


def compare(value: float, cmp: Comparator, threshold: float) -> bool:
    """value <cmp> threshold 평가."""
    if cmp is Comparator.LT:
        return value < threshold
    if cmp is Comparator.LTE:
        return value <= threshold
    if cmp is Comparator.GT:
        return value > threshold
    if cmp is Comparator.GTE:
        return value >= threshold
    return value == threshold


@dataclass(frozen=True)
class Predicate:
    """시계열 연산(count/streak)의 연도별 판정 술어."""

    cmp: Comparator
    value: float


@dataclass(frozen=True)
class Condition:
    """단일 조건의 내부 표현. op별로 사용하는 필드가 다르다 (validate_condition이 강제).

    - cmp:    metric, op="cmp", cmp, value
    - count:  metric, op="count", window, predicate, min_count
    - cagr:   metric, op="cagr", window, cmp, value
    - streak: metric, op="streak", window, predicate
    - avg:    metric, op="avg", window, cmp, value
    """

    metric: str
    op: str
    cmp: Comparator | None = None
    value: float | None = None
    window: int | None = None
    min_count: int | None = None
    predicate: Predicate | None = None
