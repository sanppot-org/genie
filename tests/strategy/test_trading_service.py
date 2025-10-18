"""TradingService 클래스 테스트"""

import datetime as dt
from unittest.mock import Mock

import pytest

from src.strategy.config import BaseStrategyConfig
from src.strategy.data.models import HalfDayCandle, Recent20DaysHalfDayCandles
from src.strategy.order_executor import ExecutionResult, OrderExecutor
from src.strategy.strategy import TradingService


@pytest.fixture
def mock_order_executor():
    """OrderExecutor 모킹"""
    executor = Mock(spec=OrderExecutor)
    # 기본 반환값 설정
    executor.buy.return_value = ExecutionResult(
        ticker="KRW-BTC",
        executed_volume=0.0002,
        executed_price=50000000.0,
        executed_amount=10000.0,
        order=Mock(),
    )
    executor.sell.return_value = ExecutionResult(
        ticker="KRW-BTC",
        executed_volume=0.0002,
        executed_price=50000000.0,
        executed_amount=10000.0,
        order=Mock(),
    )
    return executor


@pytest.fixture
def mock_config():
    """BaseStrategyConfig 모킹"""
    return BaseStrategyConfig(
        ticker="KRW-BTC",
        total_balance=100_000_000,
        allocated_balance=10_000_000,
        target_vol=0.005,
        timezone="Asia/Seoul",
    )


@pytest.fixture
def mock_clock():
    """Clock 모킹"""
    clock = Mock()
    clock.today.return_value = dt.date(2025, 1, 15)
    clock.is_morning.return_value = True
    return clock


@pytest.fixture
def mock_collector():
    """DataCollector 모킹"""
    from src.strategy.data.models import Period

    collector = Mock()
    # 기본 데이터 설정 - 20일치 오전/오후 캔들 생성
    candles = []
    base_date = dt.date(2025, 1, 1)

    for i in range(20):
        date = base_date - dt.timedelta(days=19 - i)
        # 오전 캔들
        morning = HalfDayCandle(
            date=date,
            period=Period.MORNING,
            open=50000000.0,
            high=51000000.0,
            low=49000000.0,
            close=50500000.0,
            volume=100.0,
        )
        # 오후 캔들
        afternoon = HalfDayCandle(
            date=date,
            period=Period.AFTERNOON,
            open=50500000.0,
            high=52000000.0,
            low=50000000.0,
            close=51000000.0,
            volume=120.0,
        )
        candles.extend([morning, afternoon])

    history = Recent20DaysHalfDayCandles(candles=candles)
    collector.collect_data.return_value = history
    return collector


@pytest.fixture
def trading_service(mock_order_executor, mock_config, mock_clock, mock_collector):
    """TradingService 인스턴스 생성"""
    return TradingService(mock_order_executor, mock_config, mock_clock, mock_collector)


class TestTradingServiceInitialization:
    """TradingService 초기화 테스트"""

    def test_should_initialize_with_order_executor(self, mock_order_executor, mock_config, mock_clock, mock_collector):
        """OrderExecutor를 받아서 초기화해야 한다"""
        # When
        service = TradingService(mock_order_executor, mock_config, mock_clock, mock_collector)

        # Then
        assert service._order_executor == mock_order_executor
        assert service._config == mock_config
        assert service._clock == mock_clock
        assert service._collector == mock_collector

    def test_should_initialize_cache_on_creation(self, mock_order_executor, mock_config, mock_clock, mock_collector):
        """생성 시 캐시를 초기화해야 한다"""
        # When
        service = TradingService(mock_order_executor, mock_config, mock_clock, mock_collector)

        # Then
        assert service._cache is not None
        assert service._cache.last_run_date == mock_clock.today()
        mock_collector.collect_data.assert_called_once_with(mock_config.ticker)


class TestTradingServiceVolatilityStrategy:
    """TradingService 변동성 돌파 전략 테스트"""

    def test_volatility_strategy_should_use_order_executor_buy(
            self, trading_service, mock_order_executor, mock_clock
    ):
        """변동성 돌파 전략에서 매수 시 OrderExecutor.buy()를 사용해야 한다"""
        # Given
        mock_clock.is_morning.return_value = True
        trading_service._cache.volatility_position_size = 0.1
        trading_service._cache.volatility_execution_volume = 0  # 아직 매수 전
        trading_service._cache.volatility_threshold = 49000000.0  # 낮은 임계값으로 설정

        # When
        trading_service._volatility()

        # Then
        mock_order_executor.buy.assert_called_once()
        call_args = mock_order_executor.buy.call_args
        assert call_args[0][0] == "KRW-BTC"  # ticker
        assert call_args[0][1] > 0  # amount

    def test_volatility_strategy_should_use_order_executor_sell(
            self, trading_service, mock_order_executor, mock_clock
    ):
        """변동성 돌파 전략에서 매도 시 OrderExecutor.sell()을 사용해야 한다"""
        # Given
        mock_clock.is_morning.return_value = False  # 오후
        trading_service._cache.volatility_execution_volume = 0.0002  # 매수한 수량

        # When
        trading_service._volatility()

        # Then
        mock_order_executor.sell.assert_called_once_with("KRW-BTC", 0.0002)
        assert trading_service._cache.volatility_execution_volume == 0


class TestTradingServiceMorningAfternoonStrategy:
    """TradingService 오전/오후 전략 테스트"""

    def test_morning_afternoon_strategy_should_use_order_executor_buy(
            self, trading_service, mock_order_executor, mock_clock
    ):
        """오전/오후 전략에서 매수 시 OrderExecutor.buy()를 사용해야 한다"""
        # Given
        mock_clock.is_morning.return_value = True
        trading_service._cache.morning_afternoon_execution_volume = 0  # 아직 매수 전
        # 매수 조건 충족: 전일 오후 수익률 > 0, 전일 오전 거래량 < 전일 오후 거래량
        trading_service._cache.history.yesterday_afternoon.close = 51000000.0
        trading_service._cache.history.yesterday_afternoon.open = 50000000.0
        trading_service._cache.history.yesterday_morning.volume = 100.0
        trading_service._cache.history.yesterday_afternoon.volume = 120.0

        # When
        trading_service._morning_afternoon()

        # Then
        mock_order_executor.buy.assert_called_once()
        call_args = mock_order_executor.buy.call_args
        assert call_args[0][0] == "KRW-BTC"  # ticker
        assert call_args[0][1] > 0  # amount

    def test_morning_afternoon_strategy_should_use_order_executor_sell(
            self, trading_service, mock_order_executor, mock_clock
    ):
        """오전/오후 전략에서 매도 시 OrderExecutor.sell()을 사용해야 한다"""
        # Given
        mock_clock.is_morning.return_value = False  # 오후
        trading_service._cache.morning_afternoon_execution_volume = 0.0003  # 매수한 수량

        # When
        trading_service._morning_afternoon()

        # Then
        mock_order_executor.sell.assert_called_once_with("KRW-BTC", 0.0003)
        assert trading_service._cache.morning_afternoon_execution_volume == 0


class TestTradingServiceIntegration:
    """TradingService 통합 테스트"""

    def test_should_not_call_buy_or_sell_when_conditions_not_met(
            self, trading_service, mock_order_executor, mock_clock
    ):
        """매수/매도 조건이 충족되지 않으면 주문을 실행하지 않아야 한다"""
        # Given
        mock_clock.is_morning.return_value = False  # 오후
        trading_service._cache.volatility_execution_volume = 0
        trading_service._cache.morning_afternoon_execution_volume = 0

        # When
        trading_service.run()

        # Then
        mock_order_executor.buy.assert_not_called()
        mock_order_executor.sell.assert_not_called()
