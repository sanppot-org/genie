"""전략 레지스트리 테스트"""

from dataclasses import FrozenInstanceError

import pytest

from src.backtest.registry import STRATEGY_REGISTRY, StrategySpec, get_strategy, list_strategies
from src.backtest.strategy.buy_and_hold_strategy import BuyAndHoldStrategy
from src.backtest.strategy.ema_alignment_strategy import EmaAlignmentStrategy
from src.backtest.strategy.ema_dynamic_sizer import EmaDynamicSizer
from src.backtest.strategy.ema_simple_alignment_strategy import EmaSimpleAlignmentStrategy
from src.backtest.strategy.morning_afternoon_strategy import MorningAfternoonStrategy
from src.backtest.strategy.simple_strategy import SimpleStrategy
from src.backtest.strategy.split_strategy import SplitStrategy
from src.backtest.strategy.timed_hold_strategy import TimedHoldStrategy
from src.backtest.strategy.volatility_breakout_strategy import VolatilityBreakoutStrategy


class TestRegistryIntegration:
    """레지스트리 통합 테스트 — 8개 전략 등록 확인"""

    EXPECTED_STRATEGIES = {
        "simple": (SimpleStrategy, "1d", False),
        "volatility_breakout": (VolatilityBreakoutStrategy, "1d", False),
        "ema_alignment": (EmaAlignmentStrategy, "1d", False),
        "ema_simple_alignment": (EmaSimpleAlignmentStrategy, "1d", False),
        "split": (SplitStrategy, "1d", False),
        "timed_hold": (TimedHoldStrategy, "1h", True),
        "morning_afternoon": (MorningAfternoonStrategy, "1h", False),
        "buy_and_hold": (BuyAndHoldStrategy, "1d", False),
    }

    def test_registry_has_all_eight_strategies(self):
        """레지스트리에 정확히 8개 전략이 등록되어 있어야 합니다"""
        assert len(STRATEGY_REGISTRY) == 8

    def test_all_strategies_have_correct_class_and_timeframe(self):
        """각 전략의 클래스·타임프레임·cheat_on_open이 올바르게 등록되어야 합니다"""
        for name, (expected_class, expected_tf, expected_cheat) in self.EXPECTED_STRATEGIES.items():
            spec = get_strategy(name)
            assert spec.strategy_class is expected_class, f"{name}: strategy_class 불일치"
            assert spec.timeframe == expected_tf, f"{name}: timeframe 불일치"
            assert spec.requires_cheat_on_open == expected_cheat, f"{name}: requires_cheat_on_open 불일치"

    def test_all_specs_are_strategy_spec_instances(self):
        """모든 레지스트리 값이 StrategySpec 인스턴스여야 합니다"""
        for name, spec in STRATEGY_REGISTRY.items():
            assert isinstance(spec, StrategySpec), f"{name}: StrategySpec 인스턴스 아님"

    def test_list_strategies_returns_all_names_sorted(self):
        """list_strategies()가 8개의 이름을 정렬된 순서로 반환해야 합니다"""
        names = list_strategies()
        assert len(names) == 8
        assert names == sorted(names)
        assert set(names) == set(self.EXPECTED_STRATEGIES)

    def test_ema_alignment_uses_ema_dynamic_sizer(self):
        """EmaAlignmentStrategy는 EmaDynamicSizer를 default_sizer로 가져야 합니다"""
        spec = get_strategy("ema_alignment")
        assert spec.default_sizer is not None
        assert spec.default_sizer.sizer_class is EmaDynamicSizer

    def test_ema_simple_alignment_does_not_use_ema_dynamic_sizer(self):
        """EmaSimpleAlignmentStrategy는 EmaDynamicSizer를 사용하면 안 됩니다"""
        spec = get_strategy("ema_simple_alignment")
        assert spec.default_sizer is None or spec.default_sizer.sizer_class is not EmaDynamicSizer

    def test_timed_hold_requires_cheat_on_open(self):
        """TimedHoldStrategy는 cheat_on_open이 필요합니다"""
        spec = get_strategy("timed_hold")
        assert spec.requires_cheat_on_open is True

    def test_spec_is_frozen(self):
        """StrategySpec은 frozen dataclass여야 합니다"""
        spec = get_strategy("simple")
        with pytest.raises(FrozenInstanceError):
            spec.name = "modified"  # type: ignore[misc]

    def test_registry_keys_match_spec_names(self):
        """레지스트리 dict 키와 StrategySpec.name이 일치해야 합니다"""
        for key, spec in STRATEGY_REGISTRY.items():
            assert key == spec.name, f"키 '{key}'와 spec.name '{spec.name}' 불일치"

    def test_split_manages_own_sizing(self):
        """SplitStrategy는 manages_own_sizing=True여야 합니다"""
        spec = get_strategy("split")
        assert spec.manages_own_sizing is True

    def test_get_strategy_returns_independent_default_params(self):
        """get_strategy()가 반환한 default_params를 수정해도 레지스트리 원본에 영향 없어야 합니다"""
        spec1 = get_strategy("volatility_breakout")
        spec1.default_params["k_value"] = 999.0
        spec2 = get_strategy("volatility_breakout")
        assert spec2.default_params["k_value"] != 999.0


class TestGetStrategyError:
    """잘못된 이름에 대한 ValueError 테스트"""

    def test_unknown_strategy_raises_value_error(self):
        """등록되지 않은 이름은 ValueError를 발생시켜야 합니다"""
        with pytest.raises(ValueError, match="알 수 없는 전략"):
            get_strategy("nonexistent_strategy")

    def test_error_message_contains_available_names(self):
        """오류 메시지에 사용 가능한 전략 목록이 포함되어야 합니다"""
        with pytest.raises(ValueError, match="simple"):
            get_strategy("nonexistent_strategy")
