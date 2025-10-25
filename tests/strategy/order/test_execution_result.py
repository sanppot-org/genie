from datetime import datetime

import pytest

from src.common.order_direction import OrderDirection
from src.strategy.order.execution_result import ExecutionResult
from src.upbit.model.order import OrderResult, OrderSide, OrderState, OrderType, Trade


class TestExecutionResult:
    """ExecutionResult 클래스 테스트"""

    def test_single_trade_execution(self):
        """단일 체결 시나리오 테스트"""
        # Given: 단일 체결 내역을 가진 OrderResult
        trade = Trade(
            market="KRW-BTC",
            uuid="trade-uuid-1",
            price=50000000.0,
            volume=0.01,
            funds=500000.0,
            trend="up",
            created_at=datetime.now(),
            side=OrderSide.BID,
        )

        order_result = OrderResult(
            uuid="order-uuid-1",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=500000.0,
            state=OrderState.DONE,
            market="KRW-BTC",
            created_at=datetime.now(),
            volume=None,
            remaining_volume=None,
            executed_volume=0.01,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=500.0,
            locked=0.0,
            trades_count=1,
            trades=[trade],
        )

        # When: ExecutionResult 생성
        result = ExecutionResult.buy(strategy_name="test_strategy", order_result=order_result)

        # Then: 단일 체결 정보가 정확하게 반영됨
        assert result.ticker == "KRW-BTC"
        assert result.executed_price == 50000000.0
        assert result.executed_volume == 0.01
        assert result.executed_amount == 500000.0
        assert result.order_type == OrderDirection.BUY

    def test_multiple_trades_execution(self):
        """다중 체결 시나리오 테스트 - 여러 호가에 걸친 체결"""
        # Given: 3개의 서로 다른 가격에 체결된 내역
        trades = [
            Trade(
                market="KRW-ETH",
                uuid="trade-uuid-1",
                price=3000000.0,
                volume=0.1,
                funds=300000.0,
                trend="up",
                created_at=datetime.now(),
                side=OrderSide.BID,
            ),
            Trade(
                market="KRW-ETH",
                uuid="trade-uuid-2",
                price=3010000.0,
                volume=0.15,
                funds=451500.0,
                trend="up",
                created_at=datetime.now(),
                side=OrderSide.BID,
            ),
            Trade(
                market="KRW-ETH",
                uuid="trade-uuid-3",
                price=3020000.0,
                volume=0.05,
                funds=151000.0,
                trend="up",
                created_at=datetime.now(),
                side=OrderSide.BID,
            ),
        ]

        total_volume = 0.1 + 0.15 + 0.05  # 0.3
        total_funds = 300000.0 + 451500.0 + 151000.0  # 902500.0

        order_result = OrderResult(
            uuid="order-uuid-2",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=total_funds,
            state=OrderState.DONE,
            market="KRW-ETH",
            created_at=datetime.now(),
            volume=None,
            remaining_volume=None,
            executed_volume=total_volume,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=902.5,
            locked=0.0,
            trades_count=3,
            trades=trades,
        )

        # When: ExecutionResult 생성
        result = ExecutionResult.buy(strategy_name="test_strategy", order_result=order_result)

        # Then: 모든 체결의 합산 결과가 반영됨
        assert result.ticker == "KRW-ETH"
        assert result.executed_volume == 0.3
        assert result.executed_amount == 902500.0

        # 가중평균 체결가 검증: total_funds / total_volume
        expected_avg_price = 902500.0 / 0.3
        assert result.executed_price == pytest.approx(expected_avg_price)
        assert result.order_type == OrderDirection.BUY

    def test_sell_order_multiple_trades(self):
        """매도 주문 다중 체결 테스트"""
        # Given: 매도 주문의 다중 체결
        trades = [
            Trade(
                market="KRW-BTC",
                uuid="trade-uuid-1",
                price=51000000.0,
                volume=0.005,
                funds=255000.0,
                trend="down",
                created_at=datetime.now(),
                side=OrderSide.ASK,
            ),
            Trade(
                market="KRW-BTC",
                uuid="trade-uuid-2",
                price=50990000.0,
                volume=0.003,
                funds=152970.0,
                trend="down",
                created_at=datetime.now(),
                side=OrderSide.ASK,
            ),
        ]

        total_volume = 0.005 + 0.003  # 0.008
        total_funds = 255000.0 + 152970.0  # 407970.0

        order_result = OrderResult(
            uuid="order-uuid-3",
            side=OrderSide.ASK,
            ord_type=OrderType.MARKET,
            price=None,
            state=OrderState.DONE,
            market="KRW-BTC",
            created_at=datetime.now(),
            volume=0.008,
            remaining_volume=0.0,
            executed_volume=total_volume,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=407.97,
            locked=0.0,
            trades_count=2,
            trades=trades,
        )

        # When: ExecutionResult 생성
        result = ExecutionResult.sell(strategy_name="test_strategy", order_result=order_result)

        # Then
        assert result.ticker == "KRW-BTC"
        assert result.executed_volume == 0.008
        assert result.executed_amount == 407970.0
        assert result.executed_price == pytest.approx(407970.0 / 0.008)
        assert result.order_type == OrderDirection.SELL

    def test_weighted_average_price_calculation(self):
        """가중평균 체결가 계산 정확도 검증"""
        # Given: 명확한 가중평균을 검증하기 위한 간단한 케이스
        trades = [
            Trade(
                market="KRW-BTC",
                uuid="trade-uuid-1",
                price=10000000.0,
                volume=1.0,
                funds=10000000.0,
                trend="up",
                created_at=datetime.now(),
                side=OrderSide.BID,
            ),
            Trade(
                market="KRW-BTC",
                uuid="trade-uuid-2",
                price=12000000.0,
                volume=2.0,
                funds=24000000.0,
                trend="up",
                created_at=datetime.now(),
                side=OrderSide.BID,
            ),
        ]

        # 가중평균: (10M * 1 + 12M * 2) / (1 + 2) = 34M / 3 ≈ 11,333,333.33
        total_volume = 3.0
        total_funds = 34000000.0
        expected_avg_price = total_funds / total_volume

        order_result = OrderResult(
            uuid="order-uuid-4",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=total_funds,
            state=OrderState.DONE,
            market="KRW-BTC",
            created_at=datetime.now(),
            volume=None,
            remaining_volume=None,
            executed_volume=total_volume,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=34000.0,
            locked=0.0,
            trades_count=2,
            trades=trades,
        )

        # When
        result = ExecutionResult.buy(strategy_name="test_strategy", order_result=order_result)

        # Then: 가중평균 체결가가 정확하게 계산됨
        assert result.executed_price == pytest.approx(expected_avg_price, rel=1e-9)
        assert result.executed_price == pytest.approx(11333333.333333334)
