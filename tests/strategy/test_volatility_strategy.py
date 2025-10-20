from unittest.mock import Mock, patch

import pytest

from src.common.clock import Clock
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.order.execution_result import ExecutionResult
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.volatility_strategy import VolatilityStrategy


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
def volatility_strategy(mock_order_executor, mock_config, mock_clock, mock_collector, mock_cache_manager):
    return VolatilityStrategy(
        order_executor=mock_order_executor,
        config=mock_config,
        clock=mock_clock,
        collector=mock_collector,
        cache_manager=mock_cache_manager,
    )


class TestVolatilityStrategyExecute:
    """VolatilityStrategy의 execute 메서드 테스트"""

    def test_execute_buy_when_should_buy_signal_and_not_holding(self, volatility_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """매수 시그널이 있고 아직 보유하지 않았을 때 매수 주문을 실행한다"""
        # Given: 오전이고, 아직 매수 전이고, position size > 0이고, 현재가 > 임계값
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        # 캐시 없음 (매수 가능)
        mock_cache_manager.load_strategy_cache.return_value = None

        # Mock history data
        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.05
        mock_history.yesterday_morning.range = 1000000
        mock_history.yesterday_afternoon.close = 50000000
        mock_history.calculate_ma_score.return_value = 1.0
        mock_history.calculate_morning_noise_average.return_value = 0.5
        mock_collector.collect_data.return_value = mock_history

        # Mock UpbitAPI.get_current_price to return price > threshold
        with patch("src.strategy.volatility_strategy.UpbitAPI.get_current_price") as mock_price:
            mock_price.return_value = 51000000  # > threshold (50500000)

            # Mock ExecutionResult
            execution_result = Mock(spec=ExecutionResult)
            execution_result.executed_volume = 0.001
            mock_order_executor.buy.return_value = execution_result

            # When: execute 호출
            volatility_strategy.execute()

            # Then: 매수 주문이 실행되고 캐시가 2번 저장됨 (계산 시 1번, 매수 후 1번)
            mock_order_executor.buy.assert_called_once()
            assert mock_cache_manager.save_strategy_cache.call_count == 2

    def test_execute_sell_when_no_buy_signal_and_holding(self, volatility_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """매수 시그널이 없고 보유 중일 때 매도 주문을 실행한다"""
        # Given: 오전이 아니고, 보유 중
        mock_clock.is_morning.return_value = False
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        # 캐시에 보유 수량 있음
        import datetime as dt

        from src.strategy.cache.cache_models import VolatilityStrategyCacheData

        mock_cache = VolatilityStrategyCacheData(
            execution_volume=0.001,
            last_run_date=dt.date(2024, 1, 1),
            position_size=1.0,
            threshold=50500000,
        )
        mock_cache_manager.load_strategy_cache.return_value = mock_cache

        # Mock history data (execute에서 항상 계산하므로 필요)
        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.05
        mock_history.yesterday_morning.range = 1000000
        mock_history.yesterday_afternoon.close = 50000000
        mock_history.calculate_ma_score.return_value = 1.0
        mock_history.calculate_morning_noise_average.return_value = 0.5
        mock_collector.collect_data.return_value = mock_history

        # When: execute 호출
        volatility_strategy.execute()

        # Then: 매도 주문이 실행되고 캐시가 삭제됨
        mock_order_executor.sell.assert_called_once_with("KRW-BTC", 0.001, strategy_name="volatility")
        mock_cache_manager.delete_strategy_cache.assert_called_once_with("KRW-BTC", "volatility")

    def test_execute_no_buy_when_morning_but_position_size_zero(self, volatility_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """오전이지만 포지션 크기가 0이면 매수하지 않는다"""
        # Given: 오전이고, 아직 매수 전이지만, position_size = 0
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        # 캐시 없음 (매수 가능)
        mock_cache_manager.load_strategy_cache.return_value = None

        # Mock history data - ma_score가 0이면 position_size = 0
        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.05
        mock_history.yesterday_morning.range = 1000000
        mock_history.yesterday_afternoon.close = 50000000
        mock_history.calculate_ma_score.return_value = 0  # position_size = 0
        mock_history.calculate_morning_noise_average.return_value = 0.5
        mock_collector.collect_data.return_value = mock_history

        with patch("src.strategy.volatility_strategy.UpbitAPI.get_current_price") as mock_price:
            mock_price.return_value = 51000000

            # When: execute 호출
            volatility_strategy.execute()

            # Then: 매수 주문이 실행되지 않음
            mock_order_executor.buy.assert_not_called()
            mock_order_executor.sell.assert_not_called()

    def test_execute_uses_cached_values_when_available(self, volatility_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """같은 날 재실행 시 캐시된 position_size, threshold를 사용한다"""
        # Given: 오전이고, 오늘 날짜의 캐시가 있음
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        # 오늘 날짜의 캐시 (execution_volume=0이므로 매수 가능)
        from src.strategy.cache.cache_models import VolatilityStrategyCacheData

        cached_position_size = 1.0
        cached_threshold = 50500000
        mock_cache = VolatilityStrategyCacheData(
            execution_volume=0,  # 매수 전
            last_run_date=dt.date(2024, 1, 1),
            position_size=cached_position_size,
            threshold=cached_threshold,
        )
        mock_cache_manager.load_strategy_cache.return_value = mock_cache

        # Mock UpbitAPI.get_current_price to return price > cached_threshold
        with patch("src.strategy.volatility_strategy.UpbitAPI.get_current_price") as mock_price:
            mock_price.return_value = 51000000  # > cached_threshold

            # Mock ExecutionResult
            execution_result = Mock(spec=ExecutionResult)
            execution_result.executed_volume = 0.001
            mock_order_executor.buy.return_value = execution_result

            # When: execute 호출
            volatility_strategy.execute()

            # Then: collect_data가 호출되지 않음 (캐시 사용)
            mock_collector.collect_data.assert_not_called()

            # 매수 주문 실행됨
            mock_order_executor.buy.assert_called_once()

            # 캐시 저장 시 position_size, threshold 포함
            save_call_args = mock_cache_manager.save_strategy_cache.call_args
            saved_cache = save_call_args[0][2]  # 세 번째 인자
            assert isinstance(saved_cache, VolatilityStrategyCacheData)
            assert saved_cache.position_size == cached_position_size
            assert saved_cache.threshold == cached_threshold
            assert saved_cache.execution_volume == 0.001

    def test_execute_saves_volatility_cache_data(self, volatility_strategy, mock_order_executor, mock_clock, mock_collector, mock_cache_manager):
        """매수 성공 시 VolatilityStrategyCacheData를 저장한다"""
        # Given: 매수 조건 충족
        mock_clock.is_morning.return_value = True
        import datetime as dt

        mock_clock.today.return_value = dt.date(2024, 1, 1)

        mock_cache_manager.load_strategy_cache.return_value = None

        # Mock history data
        mock_history = Mock()
        mock_history.yesterday_morning.volatility = 0.05
        mock_history.yesterday_morning.range = 1000000
        mock_history.yesterday_afternoon.close = 50000000
        mock_history.calculate_ma_score.return_value = 1.0
        mock_history.calculate_morning_noise_average.return_value = 0.5
        mock_collector.collect_data.return_value = mock_history

        with patch("src.strategy.volatility_strategy.UpbitAPI.get_current_price") as mock_price:
            mock_price.return_value = 51000000

            execution_result = Mock(spec=ExecutionResult)
            execution_result.executed_volume = 0.001
            mock_order_executor.buy.return_value = execution_result

            # When: execute 호출
            volatility_strategy.execute()

            # Then: VolatilityStrategyCacheData가 2번 저장됨 (계산 시 1번, 매수 후 1번)
            assert mock_cache_manager.save_strategy_cache.call_count == 2

            # 마지막 호출 (매수 후)의 캐시 데이터 검증
            save_call_args = mock_cache_manager.save_strategy_cache.call_args
            saved_cache = save_call_args[0][2]

            from src.strategy.cache.cache_models import VolatilityStrategyCacheData

            assert isinstance(saved_cache, VolatilityStrategyCacheData)
            assert saved_cache.execution_volume == 0.001
            assert saved_cache.last_run_date == dt.date(2024, 1, 1)
            assert saved_cache.position_size == 1.0  # target_vol / volatility * ma_score
            assert saved_cache.threshold == 50500000  # close + range * k
