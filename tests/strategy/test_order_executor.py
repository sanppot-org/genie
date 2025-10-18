"""OrderExecutor 클래스 테스트"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.strategy.order_executor import ExecutionResult, OrderExecutor
from src.upbit.model.order import OrderResult, OrderSide, OrderState, OrderType, Trade


@pytest.fixture
def mock_upbit_api():
    """UpbitAPI 모킹"""
    return Mock()


@pytest.fixture
def order_executor(mock_upbit_api):
    """OrderExecutor 인스턴스 생성"""
    return OrderExecutor(mock_upbit_api)


class TestOrderExecutorBuy:
    """OrderExecutor.buy() 메서드 테스트"""

    def test_buy_should_return_execution_result(self, order_executor, mock_upbit_api):
        """매수 주문 실행 시 ExecutionResult를 반환해야 한다"""
        # Given
        ticker = "KRW-BTC"
        amount = 10000.0
        expected_price = 50000000.0
        expected_volume = 0.0002

        mock_order = OrderResult(
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=amount,
            state=OrderState.DONE,
            market=ticker,
            created_at=datetime.now(),
            volume=None,
            remaining_volume=None,
            executed_volume=expected_volume,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=5.0,
            locked=0.0,
            trades_count=1,
            trades=[
                Trade(
                    market=ticker,
                    uuid="trade-uuid",
                    price=expected_price,
                    volume=expected_volume,
                    funds=amount,
                    trend="up",
                    created_at=datetime.now(),
                    side=OrderSide.BID,
                )
            ],
        )
        mock_upbit_api.buy_market_order_and_wait.return_value = mock_order

        # When
        result = order_executor.buy(ticker, amount)

        # Then
        assert isinstance(result, ExecutionResult)
        assert result.ticker == ticker
        assert result.executed_volume == expected_volume
        assert result.executed_price == expected_price
        assert result.executed_amount == amount
        assert result.order == mock_order
        mock_upbit_api.buy_market_order_and_wait.assert_called_once_with(ticker, amount)

    def test_buy_should_extract_execution_info_from_first_trade(self, order_executor, mock_upbit_api):
        """매수 주문 시 첫 번째 체결 정보를 사용해야 한다"""
        # Given
        ticker = "KRW-ETH"
        amount = 5000.0
        first_trade = Trade(
            market=ticker,
            uuid="trade-1",
            price=3000000.0,
            volume=0.00166667,
            funds=5000.0,
            trend="up",
            created_at=datetime.now(),
            side=OrderSide.BID,
        )
        second_trade = Trade(
            market=ticker,
            uuid="trade-2",
            price=3000100.0,
            volume=0.00001,
            funds=30.0,
            trend="up",
            created_at=datetime.now(),
            side=OrderSide.BID,
        )

        mock_order = OrderResult(
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=amount,
            state=OrderState.DONE,
            market=ticker,
            created_at=datetime.now(),
            volume=None,
            remaining_volume=None,
            executed_volume=0.00167667,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=2.5,
            locked=0.0,
            trades_count=2,
            trades=[first_trade, second_trade],
        )
        mock_upbit_api.buy_market_order_and_wait.return_value = mock_order

        # When
        result = order_executor.buy(ticker, amount)

        # Then
        assert result.executed_price == first_trade.price
        assert result.executed_volume == first_trade.volume


class TestOrderExecutorSell:
    """OrderExecutor.sell() 메서드 테스트"""

    def test_sell_should_return_execution_result(self, order_executor, mock_upbit_api):
        """매도 주문 실행 시 ExecutionResult를 반환해야 한다"""
        # Given
        ticker = "KRW-BTC"
        volume = 0.0002
        expected_price = 50000000.0
        expected_amount = expected_price * volume

        mock_order = OrderResult(
            uuid="test-uuid",
            side=OrderSide.ASK,
            ord_type=OrderType.MARKET,
            price=None,
            state=OrderState.DONE,
            market=ticker,
            created_at=datetime.now(),
            volume=volume,
            remaining_volume=0.0,
            executed_volume=volume,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=5.0,
            locked=0.0,
            trades_count=1,
            trades=[
                Trade(
                    market=ticker,
                    uuid="trade-uuid",
                    price=expected_price,
                    volume=volume,
                    funds=expected_amount,
                    trend="down",
                    created_at=datetime.now(),
                    side=OrderSide.ASK,
                )
            ],
        )
        mock_upbit_api.sell_market_order_and_wait.return_value = mock_order

        # When
        result = order_executor.sell(ticker, volume)

        # Then
        assert isinstance(result, ExecutionResult)
        assert result.ticker == ticker
        assert result.executed_volume == volume
        assert result.executed_price == expected_price
        assert result.executed_amount == expected_amount
        assert result.order == mock_order
        mock_upbit_api.sell_market_order_and_wait.assert_called_once_with(ticker, volume)

    def test_sell_should_calculate_amount_from_price_and_volume(self, order_executor, mock_upbit_api):
        """매도 주문 시 가격 * 수량으로 금액을 계산해야 한다"""
        # Given
        ticker = "KRW-ETH"
        volume = 0.01
        price = 3000000.0
        expected_amount = price * volume

        mock_order = OrderResult(
            uuid="test-uuid",
            side=OrderSide.ASK,
            ord_type=OrderType.MARKET,
            price=None,
            state=OrderState.DONE,
            market=ticker,
            created_at=datetime.now(),
            volume=volume,
            remaining_volume=0.0,
            executed_volume=volume,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=15.0,
            locked=0.0,
            trades_count=1,
            trades=[
                Trade(
                    market=ticker,
                    uuid="trade-uuid",
                    price=price,
                    volume=volume,
                    funds=expected_amount,
                    trend="down",
                    created_at=datetime.now(),
                    side=OrderSide.ASK,
                )
            ],
        )
        mock_upbit_api.sell_market_order_and_wait.return_value = mock_order

        # When
        result = order_executor.sell(ticker, volume)

        # Then
        assert result.executed_amount == expected_amount
        assert result.executed_amount == price * volume
