from dataclasses import dataclass

from src.common.order_direction import OrderDirection
from src.upbit.model.order import OrderResult


@dataclass
class ExecutionResult:
    """
    주문 체결 결과를 나타내는 클래스

    Attributes:
        ticker: 마켓 ID (예: "KRW-BTC")
        executed_volume: 체결된 수량
        executed_price: 체결된 가격
        executed_amount: 체결된 금액 (가격 * 수량)
        order: 원본 주문 정보
    """

    strategy_name: str
    order_type: OrderDirection
    ticker: str
    executed_volume: float
    executed_price: float
    executed_amount: float
    order: OrderResult

    @staticmethod
    def sell(strategy_name: str, order_result: OrderResult) -> "ExecutionResult":
        return ExecutionResult.of(
            strategy_name=strategy_name,
            order_direction=OrderDirection.SELL,
            order_result=order_result,
        )

    @staticmethod
    def buy(strategy_name: str, order_result: OrderResult) -> "ExecutionResult":
        return ExecutionResult.of(
            strategy_name=strategy_name,
            order_direction=OrderDirection.BUY,
            order_result=order_result,
        )

    @staticmethod
    def of(strategy_name: str, order_direction: OrderDirection, order_result: OrderResult) -> "ExecutionResult":
        # 모든 trades의 funds를 합산하여 총 체결 금액 계산
        total_funds = sum(trade.funds for trade in order_result.trades)

        # OrderResult.executed_volume은 이미 모든 체결량의 합계
        executed_volume = order_result.executed_volume

        # 가중평균 체결가 계산: 총 체결 금액 / 총 체결량
        average_price = total_funds / executed_volume if executed_volume > 0 else 0.0

        return ExecutionResult(
            strategy_name=strategy_name,
            order_type=order_direction,
            ticker=order_result.market,
            executed_price=average_price,
            executed_volume=executed_volume,
            executed_amount=total_funds,
            order=order_result,
        )
