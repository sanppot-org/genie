"""
Backtest module tests
"""

import backtrader as bt
import pandas as pd
import pytest

from src.backtest.backtest import (
    BacktestBuilder,
)
from src.backtest.commission_config import CommissionConfig
from src.backtest.data_feed.pandas import PandasDataFeedConfig
from src.backtest.sizer_config import SizerConfig


class TestBacktestBuilder:
    """BacktestBuilder 테스트"""

    def test_builder_default_values(self):
        """빌더가 기본값으로 생성되는지 테스트"""
        builder = BacktestBuilder()

        assert builder._initial_cash is None  # 필수값으로 변경
        assert builder._commission_config is None  # 기본값 없음
        assert builder._sizer_config is None
        assert builder._strategy_class is None
        assert builder._slippage is None
        assert builder._analyzers == []
        assert builder._data_feeds == []

    def test_builder_with_initial_cash(self):
        """초기 자본 설정이 작동하는지 테스트"""
        builder = BacktestBuilder().with_initial_cash(100_000_000)

        assert builder._initial_cash == 100_000_000

    def test_builder_with_commission(self):
        """수수료 설정이 작동하는지 테스트"""
        builder = BacktestBuilder().with_commission(CommissionConfig.stock(0.002))

        assert builder._commission_config.commission == 0.002
        assert builder._commission_config.stocklike is True

    def test_builder_with_sizer(self):
        """Sizer 설정이 작동하는지 테스트"""
        builder = BacktestBuilder().with_sizer(SizerConfig.percent(5))

        assert builder._sizer_config.sizer_class == bt.sizers.PercentSizer
        assert builder._sizer_config.params == {"percents": 5}

    def test_builder_with_strategy(self):
        """전략 설정이 작동하는지 테스트"""

        # Mock 전략 클래스 생성
        class TestStrategy(bt.Strategy):
            params = (("ma_period", 20),)

        builder = BacktestBuilder().with_strategy(TestStrategy, ma_period=20)

        assert builder._strategy_class == TestStrategy
        assert builder._strategy_params == {"ma_period": 20}

    def test_builder_with_data(self):
        """데이터 추가가 작동하는지 테스트"""
        df = pd.DataFrame(
            {
                'open': [100],
                'high': [105],
                'low': [95],
                'close': [102],
                'volume': [1000]
            },
            index=pd.DatetimeIndex(['2024-01-01'])
        )
        config = PandasDataFeedConfig.create(df)
        builder = BacktestBuilder().add_data(config)

        # add_data()는 데이터 피드를 _data_feeds에 추가
        assert len(builder._data_feeds) == 1
        assert isinstance(builder._data_feeds[0], bt.feeds.PandasData)

    def test_builder_with_slippage(self):
        """슬리피지 설정이 작동하는지 테스트"""
        builder = BacktestBuilder().with_slippage(0.0005)

        assert builder._slippage == 0.0005

    def test_builder_with_analyzer(self):
        """분석기 추가가 작동하는지 테스트"""
        builder = (
            BacktestBuilder()
            .with_analyzer(bt.analyzers.SharpeRatio, "sharpe")
            .with_analyzer(bt.analyzers.DrawDown, "drawdown")
        )

        assert len(builder._analyzers) == 2
        assert builder._analyzers[0] == (bt.analyzers.SharpeRatio, "sharpe")
        assert builder._analyzers[1] == (bt.analyzers.DrawDown, "drawdown")

    def test_builder_method_chaining(self):
        """메서드 체이닝이 작동하는지 테스트"""
        builder = (
            BacktestBuilder()
            .with_initial_cash(100_000_000)
            .with_commission(CommissionConfig.stock(0.002))
            .with_sizer(SizerConfig.percent(5))
            .with_slippage(0.0005)
        )

        assert builder._initial_cash == 100_000_000
        assert builder._commission_config.commission == 0.002
        assert builder._sizer_config.sizer_class == bt.sizers.PercentSizer
        assert builder._sizer_config.params == {"percents": 5}
        assert builder._slippage == 0.0005

    def test_builder_returns_self(self):
        """모든 with 메서드가 self를 반환하는지 테스트"""
        builder = BacktestBuilder()

        # Mock 전략
        class TestStrategy(bt.Strategy):
            pass

        assert builder.with_initial_cash(100_000_000) is builder
        assert builder.with_commission(CommissionConfig.stock(0.002)) is builder
        assert builder.with_sizer(SizerConfig.percent(5)) is builder
        assert builder.with_strategy(TestStrategy, ma_period=20) is builder
        assert builder.with_slippage(0.0005) is builder
        assert builder.with_analyzer(bt.analyzers.SharpeRatio, "sharpe") is builder

    def test_builder_add_data(self):
        """add_data 메서드가 작동하는지 테스트"""
        # Mock 데이터 생성
        mock_df = pd.DataFrame(
            {
                'open': [100, 101, 102],
                'high': [105, 106, 107],
                'low': [95, 96, 97],
                'close': [102, 103, 104],
                'volume': [1000, 1100, 1200]
            },
            index=pd.DatetimeIndex(['2024-01-01', '2024-01-02', '2024-01-03'])
        )
        config = PandasDataFeedConfig.create(mock_df)

        builder = BacktestBuilder().add_data(config)

        assert len(builder._data_feeds) == 1
        assert isinstance(builder._data_feeds[0], bt.feeds.PandasData)

    def test_builder_add_data_returns_self(self):
        """add_data 메서드가 self를 반환하는지 테스트"""
        # Mock 데이터 생성
        mock_df = pd.DataFrame(
            {
                'open': [100, 101, 102],
                'high': [105, 106, 107],
                'low': [95, 96, 97],
                'close': [102, 103, 104],
                'volume': [1000, 1100, 1200]
            },
            index=pd.DatetimeIndex(['2024-01-01', '2024-01-02', '2024-01-03'])
        )
        config = PandasDataFeedConfig.create(mock_df)

        builder = BacktestBuilder()

        assert builder.add_data(config) is builder

    def test_builder_add_multiple_data_feeds(self):
        """여러 데이터 피드를 추가할 수 있는지 테스트"""
        # Mock 데이터 생성
        btc_df = pd.DataFrame(
            {
                'open': [100, 101, 102],
                'high': [105, 106, 107],
                'low': [95, 96, 97],
                'close': [102, 103, 104],
                'volume': [1000, 1100, 1200]
            },
            index=pd.DatetimeIndex(['2024-01-01', '2024-01-02', '2024-01-03'])
        )
        eth_df = pd.DataFrame(
            {
                'open': [200, 201, 202],
                'high': [205, 206, 207],
                'low': [195, 196, 197],
                'close': [202, 203, 204],
                'volume': [2000, 2100, 2200]
            },
            index=pd.DatetimeIndex(['2024-01-01', '2024-01-02', '2024-01-03'])
        )

        btc_config = PandasDataFeedConfig.create(btc_df, name='BTC')
        eth_config = PandasDataFeedConfig.create(eth_df, name='ETH')

        builder = BacktestBuilder().add_data(btc_config).add_data(eth_config)

        assert len(builder._data_feeds) == 2
        assert isinstance(builder._data_feeds[0], bt.feeds.PandasData)
        assert isinstance(builder._data_feeds[1], bt.feeds.PandasData)
        assert builder._data_feeds[0].p.name == 'BTC'
        assert builder._data_feeds[1].p.name == 'ETH'

    def test_build_without_initial_cash_raises_error(self):
        """초기 자본 없이 build() 호출 시 ValueError 발생"""

        # Mock 전략
        class TestStrategy(bt.Strategy):
            pass

        df = pd.DataFrame(
            {
                'open': [100],
                'high': [105],
                'low': [95],
                'close': [102],
                'volume': [1000]
            },
            index=pd.DatetimeIndex(['2024-01-01'])
        )
        config = PandasDataFeedConfig.create(df)

        builder = (
            BacktestBuilder()
            .with_strategy(TestStrategy)
            .add_data(config)
        )

        with pytest.raises(ValueError, match="초기 자본이 설정되지 않았습니다"):
            builder.build()

    def test_build_without_strategy_raises_error(self):
        """전략 없이 build() 호출 시 ValueError 발생"""
        df = pd.DataFrame(
            {
                'open': [100],
                'high': [105],
                'low': [95],
                'close': [102],
                'volume': [1000]
            },
            index=pd.DatetimeIndex(['2024-01-01'])
        )
        config = PandasDataFeedConfig.create(df)

        builder = (
            BacktestBuilder()
            .with_initial_cash(1_000_000)
            .add_data(config)
        )

        with pytest.raises(ValueError, match="전략이 설정되지 않았습니다"):
            builder.build()

    def test_build_without_data_feeds_raises_error(self):
        """데이터 피드 없이 build() 호출 시 ValueError 발생"""

        # Mock 전략
        class TestStrategy(bt.Strategy):
            pass

        builder = (
            BacktestBuilder()
            .with_initial_cash(1_000_000)
            .with_strategy(TestStrategy)
        )

        with pytest.raises(ValueError, match="데이터 피드가 추가되지 않았습니다"):
            builder.build()

    def test_with_initial_cash_zero_raises_error(self):
        """초기 자본 0 전달 시 ValueError 발생"""
        with pytest.raises(ValueError, match="초기 자본은 0보다 커야 합니다"):
            BacktestBuilder().with_initial_cash(0)

    def test_with_initial_cash_negative_raises_error(self):
        """초기 자본 음수 전달 시 ValueError 발생"""
        with pytest.raises(ValueError, match="초기 자본은 0보다 커야 합니다"):
            BacktestBuilder().with_initial_cash(-1000)

    def test_with_commission_extended_parameters(self):
        """확장된 commission 파라미터 설정 테스트"""
        builder = BacktestBuilder().with_commission(
            CommissionConfig.futures(commission=0.002, margin=2000.0, mult=10.0)
        )

        assert builder._commission_config.commission == 0.002
        assert builder._commission_config.margin == 2000.0
        assert builder._commission_config.mult == 10.0
        assert builder._commission_config.stocklike is False
