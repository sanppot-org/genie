"""SizerConfig 테스트"""

import backtrader as bt

from src.backtest.sizer_config import SizerConfig


class TestSizerConfigPercent:
    """SizerConfig.percent() 테스트"""

    def test_percent_creates_config_with_correct_class(self):
        """percent() 팩터리 메서드가 올바른 Sizer 클래스를 생성하는지 테스트"""
        config = SizerConfig.percent(95)

        assert config.sizer_class == bt.sizers.PercentSizer
        assert config.params == {"percents": 95}

    def test_percent_with_different_values(self):
        """다양한 비율 값으로 생성 테스트"""
        config1 = SizerConfig.percent(10)
        config2 = SizerConfig.percent(50.5)
        config3 = SizerConfig.percent(100)

        assert config1.params == {"percents": 10}
        assert config2.params == {"percents": 50.5}
        assert config3.params == {"percents": 100}


class TestSizerConfigAllIn:
    """SizerConfig.all_in() 테스트"""

    def test_all_in_creates_config_with_correct_class(self):
        """all_in() 팩터리 메서드가 올바른 Sizer 클래스를 생성하는지 테스트"""
        config = SizerConfig.all_in()

        assert config.sizer_class == bt.sizers.AllInSizer
        assert config.params == {}


class TestSizerConfigFixed:
    """SizerConfig.fixed() 테스트"""

    def test_fixed_creates_config_with_stake_only(self):
        """fixed() 팩터리 메서드가 stake만 전달했을 때 올바르게 생성하는지 테스트"""
        config = SizerConfig.fixed(100)

        assert config.sizer_class == bt.sizers.FixedSize
        assert config.params == {"stake": 100, "tranches": 1}

    def test_fixed_creates_config_with_stake_and_tranches(self):
        """fixed() 팩터리 메서드가 stake와 tranches를 모두 전달했을 때 올바르게 생성하는지 테스트"""
        config = SizerConfig.fixed(100, tranches=5)

        assert config.sizer_class == bt.sizers.FixedSize
        assert config.params == {"stake": 100, "tranches": 5}


class TestSizerConfigCustom:
    """SizerConfig.custom() 테스트"""

    def test_custom_creates_config_with_custom_sizer(self):
        """custom() 팩터리 메서드가 커스텀 Sizer로 생성하는지 테스트"""

        class CustomSizer(bt.Sizer):
            """테스트용 커스텀 Sizer"""

            pass

        config = SizerConfig.custom(CustomSizer, param1=10, param2="value")

        assert config.sizer_class == CustomSizer
        assert config.params == {"param1": 10, "param2": "value"}

    def test_custom_creates_config_without_params(self):
        """custom() 팩터리 메서드가 파라미터 없이도 생성하는지 테스트"""

        class CustomSizer(bt.Sizer):
            """테스트용 커스텀 Sizer"""

            pass

        config = SizerConfig.custom(CustomSizer)

        assert config.sizer_class == CustomSizer
        assert config.params == {}


class TestSizerConfigDirectInstantiation:
    """SizerConfig 직접 생성 테스트"""

    def test_direct_instantiation_with_percent_sizer(self):
        """SizerConfig를 직접 생성할 수 있는지 테스트"""
        config = SizerConfig(bt.sizers.PercentSizer, percents=95)

        assert config.sizer_class == bt.sizers.PercentSizer
        assert config.params == {"percents": 95}

    def test_direct_instantiation_with_custom_sizer(self):
        """커스텀 Sizer로 직접 생성할 수 있는지 테스트"""

        class CustomSizer(bt.Sizer):
            """테스트용 커스텀 Sizer"""

            pass

        config = SizerConfig(CustomSizer, base=10, max=30)

        assert config.sizer_class == CustomSizer
        assert config.params == {"base": 10, "max": 30}
