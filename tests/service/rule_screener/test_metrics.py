"""지표 레지스트리 + 조건 검증 테스트."""

import pytest

from src.service.rule_screener.conditions import Comparator, Condition, Predicate
from src.service.rule_screener.metrics import (
    METRIC_REGISTRY,
    MetricSource,
    validate_condition,
)


class TestRegistry:
    def test_known_metrics_present(self) -> None:
        assert METRIC_REGISTRY["bsop_prti"].source is MetricSource.INCOME_ANNUAL
        assert METRIC_REGISTRY["bsop_prti"].is_timeseries is True
        assert METRIC_REGISTRY["per"].source is MetricSource.FUNDAMENTAL
        assert METRIC_REGISTRY["per"].is_timeseries is False
        assert METRIC_REGISTRY["total_score"].source is MetricSource.SCORE
        assert METRIC_REGISTRY["eps"].source is MetricSource.RATIO_ANNUAL


class TestValidateCondition:
    def test_unknown_metric_rejected(self) -> None:
        with pytest.raises(ValueError, match="알 수 없는 지표"):
            validate_condition(Condition(metric="nope", op="cmp", cmp=Comparator.LT, value=1.0))

    def test_timeseries_op_on_scalar_metric_rejected(self) -> None:
        with pytest.raises(ValueError, match="시계열"):
            validate_condition(Condition(metric="per", op="count", window=5,
                                         predicate=Predicate(Comparator.GT, 0.0), min_count=4))

    def test_cmp_on_timeseries_metric_rejected(self) -> None:
        with pytest.raises(ValueError, match="시계열"):
            validate_condition(Condition(metric="bsop_prti", op="cmp", cmp=Comparator.GT, value=0.0))

    def test_count_requires_window_predicate_mincount(self) -> None:
        with pytest.raises(ValueError):
            validate_condition(Condition(metric="bsop_prti", op="count", window=5))

    def test_cagr_window_must_be_at_least_2(self) -> None:
        with pytest.raises(ValueError, match="cagr"):
            validate_condition(Condition(metric="eps", op="cagr", window=1,
                                         cmp=Comparator.GT, value=0.0))

    def test_count_min_count_must_not_exceed_window(self) -> None:
        with pytest.raises(ValueError, match="min_count"):
            validate_condition(Condition(metric="bsop_prti", op="count", window=3,
                                         predicate=Predicate(Comparator.GT, 0.0), min_count=4))

    def test_valid_conditions_pass(self) -> None:
        validate_condition(Condition(metric="bsop_prti", op="count", window=5,
                                     predicate=Predicate(Comparator.GT, 0.0), min_count=4))
        validate_condition(Condition(metric="eps", op="cagr", window=5,
                                     cmp=Comparator.GT, value=0.0))
        validate_condition(Condition(metric="per", op="cmp", cmp=Comparator.LT, value=15.0))
        validate_condition(Condition(metric="roe", op="avg", window=3,
                                     cmp=Comparator.GTE, value=10.0))
        validate_condition(Condition(metric="bsop_prti", op="streak", window=5,
                                     predicate=Predicate(Comparator.GT, 0.0)))
