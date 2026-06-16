"""규칙 엔진 순수 연산자 경계값 테스트."""

from src.service.rule_screener.conditions import Comparator, Predicate
from src.service.rule_screener.operators import (
    eval_avg,
    eval_cagr,
    eval_cmp,
    eval_count,
    eval_streak,
)

POS = Predicate(cmp=Comparator.GT, value=0.0)  # "흑자"(>0)


class TestEvalCmp:
    def test_none_scalar_is_insufficient(self) -> None:
        r = eval_cmp(None, Comparator.LT, 10.0)
        assert r.insufficient is True
        assert r.passed is False

    def test_pass_and_fail(self) -> None:
        assert eval_cmp(9.0, Comparator.LT, 10.0).passed is True
        assert eval_cmp(10.0, Comparator.LT, 10.0).passed is False
        assert eval_cmp(9.0, Comparator.LT, 10.0).value == 9.0


class TestEvalCount:
    def test_insufficient_when_fewer_than_window(self) -> None:
        r = eval_count([10.0, 5.0], window=5, predicate=POS, min_count=4)
        assert r.insufficient is True
        assert r.passed is False

    def test_counts_recent_window_only(self) -> None:
        # 최신순: [흑,흑,흑,흑,적] → 최근5 중 4 흑자
        r = eval_count([1.0, 1.0, 1.0, 1.0, -1.0], window=5, predicate=POS, min_count=4)
        assert r.passed is True
        assert r.value == 4.0

    def test_below_min_count_fails(self) -> None:
        r = eval_count([1.0, 1.0, 1.0, -1.0, -1.0], window=5, predicate=POS, min_count=4)
        assert r.passed is False
        assert r.value == 3.0

    def test_uses_only_most_recent_window(self) -> None:
        # 6개 중 최근 5개만: [적,흑,흑,흑,흑](최신순) → 4 흑자, 6번째(오래된 흑자)는 무시
        r = eval_count([-1.0, 1.0, 1.0, 1.0, 1.0, 1.0], window=5, predicate=POS, min_count=5)
        assert r.passed is False
        assert r.value == 4.0

    def test_none_within_window_is_insufficient(self) -> None:
        # 최근 5년 중 한 해가 NULL → 과거값으로 메우지 않고 데이터부족 처리
        r = eval_count([1.0, None, 1.0, 1.0, 1.0, 1.0], window=5, predicate=POS, min_count=4)
        assert r.insufficient is True
        assert r.passed is False

    def test_negative_predicate_counts_deficits(self) -> None:
        # "적자(<0) 2년 이상": 최근5 [적,적,흑,흑,흑] → 적자 2 → 통과
        neg = Predicate(cmp=Comparator.LT, value=0.0)
        r = eval_count([-1.0, -1.0, 1.0, 1.0, 1.0], window=5, predicate=neg, min_count=2)
        assert r.passed is True
        assert r.value == 2.0


class TestEvalStreak:
    def test_all_window_satisfy_passes(self) -> None:
        r = eval_streak([1.0, 1.0, 1.0], window=3, predicate=POS)
        assert r.passed is True
        assert r.value == 3.0

    def test_break_in_window_fails(self) -> None:
        r = eval_streak([1.0, -1.0, 1.0], window=3, predicate=POS)
        assert r.passed is False
        assert r.value == 0.0

    def test_insufficient(self) -> None:
        r = eval_streak([1.0, 1.0], window=3, predicate=POS)
        assert r.insufficient is True


class TestEvalCagr:
    def test_positive_growth(self) -> None:
        # 최신순 [200, 100], window=2 → CAGR = 200/100 - 1 = 1.0
        r = eval_cagr([200.0, 100.0], window=2, cmp=Comparator.GT, threshold=0.0)
        assert r.passed is True
        assert abs(r.value - 1.0) < 1e-9

    def test_negative_base_is_undefined_and_fails(self) -> None:
        # 적자→흑자: oldest<=0 → CAGR 무의미 → 탈락(insufficient 아님)
        r = eval_cagr([100.0, -50.0], window=2, cmp=Comparator.GT, threshold=0.0)
        assert r.passed is False
        assert r.insufficient is False
        assert r.value is None

    def test_insufficient(self) -> None:
        r = eval_cagr([100.0], window=5, cmp=Comparator.GT, threshold=0.0)
        assert r.insufficient is True


class TestEvalAvg:
    def test_mean_over_window(self) -> None:
        r = eval_avg([10.0, 20.0, 30.0], window=3, cmp=Comparator.GTE, threshold=20.0)
        assert r.passed is True
        assert r.value == 20.0

    def test_insufficient(self) -> None:
        r = eval_avg([10.0], window=3, cmp=Comparator.GTE, threshold=20.0)
        assert r.insufficient is True
