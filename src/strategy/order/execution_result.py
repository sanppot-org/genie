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
        return ExecutionResult(
            strategy_name=strategy_name,
            order_type=order_direction,
            ticker=order_result.trades[0].market,
            executed_price=order_result.trades[0].price,
            executed_volume=order_result.trades[0].volume,
            executed_amount=order_result.trades[0].funds,
            order=order_result,
        )
