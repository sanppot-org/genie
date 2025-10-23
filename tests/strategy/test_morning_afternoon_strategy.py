from unittest.mock import Mock

import pytest

from src.common.clock import Clock
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.morning_afternoon_strategy import MorningAfternoonStrategy
from src.strategy.order.execution_result import ExecutionResult
from src.strategy.order.order_executor import OrderExecutor


@pytest.fixture
def mock_order_executor():
    return Mock(spec=OrderExecutor)


@pytest.fixture
def mock_config():
    config = Mock(spec=BaseStrategyConfig)
    config.ticker = "KRW-BTC"
    config.total_balance = 1000000
    config.allocated_balance = 100000
    config.target_vol = 0.05
    return config


@pytest.fixture
def mock_clock():
    return Mock(spec=Clock)


@pytest.fixture
def mock_collector():
    return Mock(spec=DataCollector)


@pytest.fixture
def mock_cache_manager():
    return Mock(spec=CacheManager)


@pytest.fixture
def morning_afternoon_strategy(mock_order_executor, mock_config, mock_clock, mock_collector, mock_cache_manager):
    return MorningAfternoonStrategy(
        order_executor=mock_order_executor,
        config=mock_config,
        clock=mock_clock,
        collector=mock_collector,
        cache_manager=mock_cache_manager,
    )


class TestMorningAfternoonStrategyExecute:
    """MorningAfternoonStrategy의 execute 메서드 테스트"""

    def test_execute_buy_when_should_buy_signal_and_not_holding(self, morning_afternoon_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """매수 시그널이 있고 아직 보유하지 않았을 때 매수 주문을 실행한다"""
        # Given: 오전이고, 아직 매수 전이고, 전일 오후 수익률 > 0, 전일 오전 거래량 < 전일 오후 거래량
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        # 캐시 없음 (매수 가능)
        mock_cache_manager.load_strategy_cache.return_value = None

        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.05
        mock_history.yesterday_morning.volume = 100
        mock_history.yesterday_afternoon.return_rate = 0.01
        mock_history.yesterday_afternoon.volume = 200
        mock_collector.collect_data.return_value = mock_history

        # Mock ExecutionResult
        execution_result = Mock(spec=ExecutionResult)
        execution_result.executed_volume = 0.001
        mock_order_executor.buy.return_value = execution_result

        # When: execute 호출
        morning_afternoon_strategy.execute()

        # Then: 매수 주문이 실행되고 캐시가 저장됨
        mock_order_executor.buy.assert_called_once()
        mock_cache_manager.save_strategy_cache.assert_called_once()

    def test_execute_sell_when_no_buy_signal_and_holding(self, morning_afternoon_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """매수 시그널이 없고 보유 중일 때 매도 주문을 실행한다"""
        # Given: 오전이 아니고, 보유 중
        mock_clock.is_morning.return_value = False
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        # 캐시에 보유 수량 있음
        import datetime as dt

        from src.strategy.cache.cache_models import StrategyCacheData

        mock_cache = StrategyCacheData(execution_volume=0.001, last_run_date=dt.date(2024, 1, 1))
        mock_cache_manager.load_strategy_cache.return_value = mock_cache

        mock_history = Mock()
        mock_history.yesterday_morning.volume = 100
        mock_history.yesterday_afternoon.return_rate = 0.01
        mock_history.yesterday_afternoon.volume = 200
        mock_collector.collect_data.return_value = mock_history

        # When: execute 호출
        morning_afternoon_strategy.execute()

        # Then: 매도 주문이 실행되고 캐시가 삭제됨
        mock_order_executor.sell.assert_called_once_with("KRW-BTC", 0.001, strategy_name="morning_afternoon")
        mock_cache_manager.delete_strategy_cache.assert_called_once_with("KRW-BTC", "morning_afternoon")

    def test_execute_no_buy_when_yesterday_afternoon_return_rate_negative(self, morning_afternoon_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """전일 오후 수익률이 음수면 매수하지 않는다"""
        # Given: 오전이고, 아직 매수 전이지만, 전일 오후 수익률이 음수
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        # 캐시 없음 (매수 가능)
        mock_cache_manager.load_strategy_cache.return_value = None

        mock_history = Mock()
        mock_history.yesterday_morning.volume = 100
        mock_history.yesterday_afternoon.return_rate = -0.01  # 음수
        mock_history.yesterday_afternoon.volume = 200
        mock_collector.collect_data.return_value = mock_history

        # When: execute 호출
        morning_afternoon_strategy.execute()

        # Then: 매수 주문이 실행되지 않음
        mock_order_executor.buy.assert_not_called()
        mock_order_executor.sell.assert_not_called()


class TestMorningAfternoonStrategyPositionSize:
    """MorningAfternoonStrategy의 position_size 계산 테스트"""

    def test_position_size_with_normal_volatility(self, morning_afternoon_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager, mock_config):
        """정상적인 변동성일 때 position_size가 올바르게 계산된다"""
        # Given: target_vol=0.05, volatility=0.05
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)
        mock_cache_manager.load_strategy_cache.return_value = None

        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.05
        mock_history.yesterday_morning.volume = 100
        mock_history.yesterday_afternoon.return_rate = 0.01
        mock_history.yesterday_afternoon.volume = 200
        mock_collector.collect_data.return_value = mock_history

        execution_result = Mock(spec=ExecutionResult)
        execution_result.executed_volume = 0.001
        mock_order_executor.buy.return_value = execution_result

        # When: execute 호출
        morning_afternoon_strategy.execute()

        # Then: position_size = 0.05 / 0.05 = 1.0, amount = min(1000000 * 1.0, 100000) = 100000
        mock_order_executor.buy.assert_called_once_with("KRW-BTC", 100000, strategy_name="morning_afternoon")

    def test_position_size_clamped_to_one_with_low_volatility(self, morning_afternoon_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager, mock_config):
        """변동성이 낮을 때 position_size가 1.0으로 제한된다"""
        # Given: target_vol=0.05, volatility=0.001 → position_size = 0.05 / 0.01 = 5.0 → clamped to 1.0
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)
        mock_cache_manager.load_strategy_cache.return_value = None

        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.001
        mock_history.yesterday_morning.volume = 100
        mock_history.yesterday_afternoon.return_rate = 0.01
        mock_history.yesterday_afternoon.volume = 200
        mock_collector.collect_data.return_value = mock_history

        execution_result = Mock(spec=ExecutionResult)
        execution_result.executed_volume = 0.001
        mock_order_executor.buy.return_value = execution_result

        # When: execute 호출
        morning_afternoon_strategy.execute()

        # Then: position_size clamped to 1.0, amount = min(1000000 * 1.0, 100000) = 100000
        mock_order_executor.buy.assert_called_once_with("KRW-BTC", 100000, strategy_name="morning_afternoon")

    def test_position_size_with_high_volatility(self, morning_afternoon_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager, mock_config):
        """변동성이 높을 때 position_size가 작아진다"""
        # Given: target_vol=0.05, volatility=0.1 → position_size = 0.05 / 0.1 = 0.5
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)
        mock_cache_manager.load_strategy_cache.return_value = None

        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.1
        mock_history.yesterday_morning.volume = 100
        mock_history.yesterday_afternoon.return_rate = 0.01
        mock_history.yesterday_afternoon.volume = 200
        mock_collector.collect_data.return_value = mock_history

        execution_result = Mock(spec=ExecutionResult)
        execution_result.executed_volume = 0.001
        mock_order_executor.buy.return_value = execution_result

        # When: execute 호출
        morning_afternoon_strategy.execute()

        # Then: position_size = 0.5, amount = min(1000000 * 0.5, 100000) = 100000
        mock_order_executor.buy.assert_called_once_with("KRW-BTC", 100000, strategy_name="morning_afternoon")
