"""주문 알림 모델"""

from pydantic import BaseModel

from src.common.order_direction import OrderDirection
from src.strategy.order.execution_result import ExecutionResult


class OrderNotification(BaseModel):
    """
    Slack 주문 알림에 필요한 정보

    Attributes:
        order_type: 주문 타입 ("매수" 또는 "매도")
        ticker: 마켓 ID (예: "KRW-BTC")
        execution_volume: 체결된 수량
        execution_price: 체결된 가격
        funds: 체결된 금액
    """

    order_type: OrderDirection
    ticker: str
    execution_volume: float
    execution_price: float
    funds: float

    def to_message(self) -> str:
        """
        주문 알림 메시지를 생성한다

        Returns:
            str: 포맷팅된 주문 알림 메시지
        """
        return (
            f"✅ {self.order_type.value} 완료: {self.ticker}\n"
            f"수량: {self.execution_volume:.8f}\n"
            f"가격: {self.execution_price:,.4f}원\n"
            f"금액: {self.funds:,.4f}원"
        )

    @staticmethod
    def from_result(result: ExecutionResult) -> "OrderNotification":
        return OrderNotification(
            order_type=result.order_type,
            ticker=result.ticker,
            execution_volume=result.executed_volume,
            execution_price=result.executed_price,
            funds=result.executed_amount,
        )
