"""OrderExecutor 클래스 테스트"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.common.google_sheet.trade_record import TradeRecord
from src.common.order_direction import OrderDirection
from src.strategy.order.order_executor import ExecutionResult, OrderExecutor
from src.upbit.model.order import OrderResult, OrderSide, OrderState, OrderType, Trade


@pytest.fixture
def mock_upbit_api():
    """UpbitAPI 모킹"""
    return Mock()


@pytest.fixture
def order_executor(mock_upbit_api):
    """OrderExecutor 인스턴스 생성"""
    return OrderExecutor(mock_upbit_api)


@pytest.fixture
def mock_google_sheet_client():
    """GoogleSheetClient 모킹"""
    return Mock()


@pytest.fixture
def order_executor_with_sheet(mock_upbit_api, mock_google_sheet_client):
    """GoogleSheetClient가 주입된 OrderExecutor 인스턴스 생성"""
    return OrderExecutor(mock_upbit_api, mock_google_sheet_client)


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

    def test_buy_should_record_to_sheet_when_sheet_client_exists(
            self, order_executor_with_sheet, mock_upbit_api, mock_google_sheet_client
    ):
        """GoogleSheetClient가 주입된 경우 매수 시 기록해야 한다"""
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
        result = order_executor_with_sheet.buy(ticker, amount)

        # Then
        mock_google_sheet_client.append_order_result.assert_called_once()
        execution_result = mock_google_sheet_client.append_order_result.call_args[0][0]
        assert execution_result.strategy_name == "Unknown"  # strategy_name (기본값)
        assert execution_result.order_type == OrderDirection.BUY  # order_type
        assert execution_result.ticker == ticker
        assert execution_result.executed_volume == expected_volume
        assert execution_result.executed_price == expected_price
        assert execution_result.executed_amount == amount

    def test_buy_should_record_strategy_name_when_provided(
            self, order_executor_with_sheet, mock_upbit_api, mock_google_sheet_client
    ):
        """strategy_name을 전달하면 해당 이름이 기록되어야 한다"""
        # Given
        ticker = "KRW-BTC"
        amount = 10000.0
        strategy_name = "변동성돌파"
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
        result = order_executor_with_sheet.buy(ticker, amount, strategy_name=strategy_name)

        # Then
        mock_google_sheet_client.append_order_result.assert_called_once()
        execution_result = mock_google_sheet_client.append_order_result.call_args[0][0]
        assert execution_result.strategy_name == strategy_name
        assert execution_result.order_type == OrderDirection.BUY
        assert execution_result.ticker == ticker
        assert execution_result.executed_volume == expected_volume
        assert execution_result.executed_price == expected_price
        assert execution_result.executed_amount == amount

    def test_buy_should_not_record_when_sheet_client_is_none(
            self, order_executor, mock_upbit_api
    ):
        """GoogleSheetClient가 None인 경우 매수 시 기록하지 않아야 한다"""
        # Given
        ticker = "KRW-BTC"
        amount = 10000.0

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
            executed_volume=0.0002,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=5.0,
            locked=0.0,
            trades_count=1,
            trades=[
                Trade(
                    market=ticker,
                    uuid="trade-uuid",
                    price=50000000.0,
                    volume=0.0002,
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
        # GoogleSheetClient가 None이므로 에러 없이 정상 동작해야 함


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

    def test_sell_should_record_to_sheet_when_sheet_client_exists(
            self, order_executor_with_sheet, mock_upbit_api, mock_google_sheet_client
    ):
        """GoogleSheetClient가 주입된 경우 매도 시 기록해야 한다"""
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
        result = order_executor_with_sheet.sell(ticker, volume)

        # Then
        mock_google_sheet_client.append_order_result.assert_called_once()
        execution_result = mock_google_sheet_client.append_order_result.call_args[0][0]
        assert execution_result.strategy_name == "Unknown"  # strategy_name (기본값)
        assert execution_result.order_type == OrderDirection.SELL  # order_type
        assert execution_result.ticker == ticker
        assert execution_result.executed_volume == volume
        assert execution_result.executed_price == expected_price
        assert execution_result.executed_amount == expected_amount

    def test_sell_should_record_strategy_name_when_provided(
            self, order_executor_with_sheet, mock_upbit_api, mock_google_sheet_client
    ):
        """strategy_name을 전달하면 해당 이름이 기록되어야 한다"""
        # Given
        ticker = "KRW-BTC"
        volume = 0.0002
        strategy_name = "오전오후"
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
        result = order_executor_with_sheet.sell(ticker, volume, strategy_name=strategy_name)

        # Then
        mock_google_sheet_client.append_order_result.assert_called_once()
        execution_result = mock_google_sheet_client.append_order_result.call_args[0][0]
        assert execution_result.strategy_name == strategy_name
        assert execution_result.order_type == OrderDirection.SELL
        assert execution_result.ticker == ticker
        assert execution_result.executed_volume == volume
        assert execution_result.executed_price == expected_price
        assert execution_result.executed_amount == expected_amount

    def test_sell_should_not_record_when_sheet_client_is_none(
            self, order_executor, mock_upbit_api
    ):
        """GoogleSheetClient가 None인 경우 매도 시 기록하지 않아야 한다"""
        # Given
        ticker = "KRW-BTC"
        volume = 0.0002

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
                    price=50000000.0,
                    volume=volume,
                    funds=10000.0,
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
        # GoogleSheetClient가 None이므로 에러 없이 정상 동작해야 함


class TestTradeRecord:
    """TradeRecord 모델 테스트"""

    def test_trade_record_should_create_with_all_fields(self):
        """모든 필드로 TradeRecord를 생성할 수 있어야 한다"""
        # Given
        strategy_name = "변동성돌파"
        order_type = OrderDirection.BUY.value
        ticker = "KRW-BTC"
        executed_volume = 0.0002
        executed_price = 50000000.0
        executed_amount = 10000.0

        # When
        record = TradeRecord(
            strategy_name=strategy_name,
            order_type=order_type,
            ticker=ticker,
            executed_volume=executed_volume,
            executed_price=executed_price,
            executed_amount=executed_amount,
        )

        # Then
        assert record.timestamp is not None  # timestamp는 자동 생성
        assert record.strategy_name == strategy_name
        assert record.order_type == order_type
        assert record.ticker == ticker
        assert record.executed_volume == executed_volume
        assert record.executed_price == executed_price
        assert record.executed_amount == executed_amount

    def test_trade_record_to_list_should_return_ordered_list(self):
        """to_list()는 정렬된 리스트를 반환해야 한다"""
        # Given
        record = TradeRecord(
            strategy_name="변동성돌파",
            order_type="매수",
            ticker="KRW-BTC",
            executed_volume=0.0002,
            executed_price=50000000.0,
            executed_amount=10000.0,
        )

        # When
        result = record.to_list()

        # Then
        assert len(result) == 7
        assert isinstance(result[0], str)  # timestamp (자동 생성)
        assert result[1] == "변동성돌파"
        assert result[2] == "매수"
        assert result[3] == "KRW-BTC"
        assert result[4] == 0.0002
        assert result[5] == 50000000.0
        assert result[6] == 10000.0

    def test_trade_record_to_list_should_maintain_field_order(self):
        """to_list()는 필드 순서를 유지해야 한다"""
        # Given
        record = TradeRecord(
            strategy_name="오전오후",
            order_type="매도",
            ticker="KRW-ETH",
            executed_volume=0.05,
            executed_price=3000000.0,
            executed_amount=150000.0,
        )

        # When
        result = record.to_list()

        # Then
        assert len(result) == 7
        assert isinstance(result[0], str)  # timestamp (자동 생성)
        assert result[1] == "오전오후"  # strategy_name
        assert result[2] == "매도"  # order_type
        assert result[3] == "KRW-ETH"  # ticker
        assert result[4] == 0.05  # executed_volume
        assert result[5] == 3000000.0  # executed_price
        assert result[6] == 150000.0  # executed_amount
