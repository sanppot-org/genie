"""규칙 엔진 순수 연산자. DB·도메인 의존 없음.

시계열 입력 `series`는 **최신순(most-recent-first)** 리스트이며 NULL 연도는 None으로
**제거하지 않고 위치 보존**한다. 각 연산은 `series[:window]`로 최근 N년을 먼저 자른 뒤,
그 윈도우 안에 None이 있거나 길이가 window 미만이면 insufficient → 호출부가 종목 제외.
(이렇게 해야 "최근 N년"이 실제 최근 N개 결산을 가리킨다 — 과거 값이 NULL 자리를 메우지 않음.)
"""

from dataclasses import dataclass

from src.service.rule_screener.conditions import Comparator, Predicate, compare


@dataclass(frozen=True)
class OpResult:
    """연산 결과. value는 표시용 계산값(count/cagr/avg 등); insufficient면 None."""

    passed: bool
    value: float | None
    insufficient: bool


def _window_values(series: list[float | None], window: int) -> list[float] | None:
    """최근 window개를 자른 뒤 None/부족이면 None 반환(=insufficient), 아니면 float 리스트."""
    recent = series[:window]
    if len(recent) < window or any(v is None for v in recent):
        return None
    return [v for v in recent if v is not None]  # mypy 좁히기 (위 guard로 None 없음)


def eval_cmp(scalar: float | None, cmp: Comparator, threshold: float) -> OpResult:
    """스칼라 비교. None이면 데이터 부족."""
    if scalar is None:
        return OpResult(passed=False, value=None, insufficient=True)
    return OpResult(passed=compare(scalar, cmp, threshold), value=scalar, insufficient=False)


def eval_count(series: list[float | None], window: int, predicate: Predicate, min_count: int) -> OpResult:
    """최근 window년 중 predicate 만족 연도 수 >= min_count."""
    vals = _window_values(series, window)
    if vals is None:
        return OpResult(passed=False, value=None, insufficient=True)
    cnt = sum(1 for v in vals if compare(v, predicate.cmp, predicate.value))
    return OpResult(passed=cnt >= min_count, value=float(cnt), insufficient=False)


def eval_streak(series: list[float | None], window: int, predicate: Predicate) -> OpResult:
    """최근 window년 연속(전부) predicate 만족."""
    vals = _window_values(series, window)
    if vals is None:
        return OpResult(passed=False, value=None, insufficient=True)
    ok = all(compare(v, predicate.cmp, predicate.value) for v in vals)
    return OpResult(passed=ok, value=float(window) if ok else 0.0, insufficient=False)


def eval_cagr(series: list[float | None], window: int, cmp: Comparator, threshold: float) -> OpResult:
    """최근 window년 CAGR 비교. 시작/끝 값 <=0 이면 무의미 → 탈락(데이터부족 아님)."""
    vals = _window_values(series, window)
    if vals is None:
        return OpResult(passed=False, value=None, insufficient=True)
    newest, oldest = vals[0], vals[window - 1]
    if oldest <= 0 or newest <= 0:
        return OpResult(passed=False, value=None, insufficient=False)
    cagr = (newest / oldest) ** (1 / (window - 1)) - 1
    return OpResult(passed=compare(cagr, cmp, threshold), value=cagr, insufficient=False)


def eval_avg(series: list[float | None], window: int, cmp: Comparator, threshold: float) -> OpResult:
    """최근 window년 평균 비교."""
    vals = _window_values(series, window)
    if vals is None:
        return OpResult(passed=False, value=None, insufficient=True)
    mean = sum(vals) / window
    return OpResult(passed=compare(mean, cmp, threshold), value=mean, insufficient=False)
