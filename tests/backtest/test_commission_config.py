"""CommissionConfig 테스트"""

from src.backtest.commission_config import CommissionConfig


class TestCommissionConfigStock:
    """CommissionConfig.stock() 테스트"""

    def test_stock_creates_config_with_correct_params(self):
        """stock() 팩터리 메서드가 올바른 파라미터로 생성하는지 테스트"""
        config = CommissionConfig.stock(0.0005)

        assert config.commission == 0.0005
        assert config.margin is None
        assert config.mult == 1.0
        assert config.stocklike is True

    def test_stock_with_different_commission_rates(self):
        """다양한 수수료율로 생성 테스트"""
        config1 = CommissionConfig.stock(0.001)
        config2 = CommissionConfig.stock(0.002)
        config3 = CommissionConfig.stock(0.0005)

        assert config1.commission == 0.001
        assert config2.commission == 0.002
        assert config3.commission == 0.0005


class TestCommissionConfigFutures:
    """CommissionConfig.futures() 테스트"""

    def test_futures_creates_config_with_margin(self):
        """futures() 팩터리 메서드가 마진 포함하여 생성하는지 테스트"""
        config = CommissionConfig.futures(0.002, margin=2000)

        assert config.commission == 0.002
        assert config.margin == 2000
        assert config.mult == 1.0
        assert config.stocklike is False

    def test_futures_creates_config_with_margin_and_mult(self):
        """futures() 팩터리 메서드가 마진과 승수 포함하여 생성하는지 테스트"""
        config = CommissionConfig.futures(0.002, margin=2000, mult=10)

        assert config.commission == 0.002
        assert config.margin == 2000
        assert config.mult == 10
        assert config.stocklike is False


class TestCommissionConfigCustom:
    """CommissionConfig.custom() 테스트"""

    def test_custom_creates_config_with_all_params(self):
        """custom() 팩터리 메서드가 모든 파라미터로 생성하는지 테스트"""
        config = CommissionConfig.custom(
            commission=0.001, margin=1000, mult=5, stocklike=False
        )

        assert config.commission == 0.001
        assert config.margin == 1000
        assert config.mult == 5
        assert config.stocklike is False

    def test_custom_creates_config_with_partial_params(self):
        """custom() 팩터리 메서드가 일부 파라미터만으로 생성하는지 테스트"""
        config = CommissionConfig.custom(commission=0.001, mult=1.5)

        assert config.commission == 0.001
        assert config.margin is None
        assert config.mult == 1.5
        assert config.stocklike is True

    def test_custom_creates_config_without_optional_params(self):
        """custom() 팩터리 메서드가 필수 파라미터만으로 생성하는지 테스트"""
        config = CommissionConfig.custom(commission=0.002)

        assert config.commission == 0.002
        assert config.margin is None
        assert config.mult == 1.0
        assert config.stocklike is True


class TestCommissionConfigToKwargs:
    """CommissionConfig.to_kwargs() 테스트"""

    def test_to_kwargs_without_margin(self):
        """margin이 없을 때 to_kwargs() 반환값 테스트"""
        config = CommissionConfig.stock(0.002)
        kwargs = config.to_kwargs()

        assert kwargs == {
            "commission": 0.002,
            "mult": 1.0,
            "stocklike": True,
        }
        assert "margin" not in kwargs

    def test_to_kwargs_with_margin(self):
        """margin이 있을 때 to_kwargs() 반환값 테스트"""
        config = CommissionConfig.futures(0.002, margin=2000, mult=10)
        kwargs = config.to_kwargs()

        assert kwargs == {
            "commission": 0.002,
            "margin": 2000,
            "mult": 10,
            "stocklike": False,
        }

    def test_to_kwargs_with_custom_params(self):
        """커스텀 파라미터로 to_kwargs() 반환값 테스트"""
        config = CommissionConfig.custom(commission=0.001, mult=1.5)
        kwargs = config.to_kwargs()

        assert kwargs == {
            "commission": 0.001,
            "mult": 1.5,
            "stocklike": True,
        }
        assert "margin" not in kwargs


class TestCommissionConfigDirectInstantiation:
    """CommissionConfig 직접 생성 테스트"""

    def test_direct_instantiation_with_all_params(self):
        """모든 파라미터로 직접 생성 테스트"""
        config = CommissionConfig(
            commission=0.002, margin=2000, mult=10, stocklike=False
        )

        assert config.commission == 0.002
        assert config.margin == 2000
        assert config.mult == 10
        assert config.stocklike is False

    def test_direct_instantiation_with_defaults(self):
        """기본값으로 직접 생성 테스트"""
        config = CommissionConfig(commission=0.001)

        assert config.commission == 0.001
        assert config.margin is None
        assert config.mult == 1.0
        assert config.stocklike is True
