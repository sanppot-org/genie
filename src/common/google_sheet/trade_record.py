"""거래 기록 모델"""
from datetime import datetime

from pydantic import BaseModel, Field

from src.common.order_direction import OrderDirection
from src.constants import KST
from src.strategy.order.execution_result import ExecutionResult


class TradeRecord(BaseModel):
    """
    Google Sheet에 기록할 거래 기록

    Attributes:
        timestamp: 거래 시간 (예: "2025-01-15 10:30:00")
        strategy_name: 전략 이름 (예: "변동성돌파", "오전오후")
        order_type: 주문 타입 ("매수" 또는 "매도")
        ticker: 마켓 ID (예: "KRW-BTC")
        executed_volume: 체결된 수량
        executed_price: 체결된 가격
        executed_amount: 체결된 금액
    """

    timestamp: datetime = Field(default=datetime.now(KST))
    strategy_name: str
    order_type: OrderDirection
    ticker: str
    executed_volume: float
    executed_price: float
    executed_amount: float

    def to_list(self) -> list:
        """Google Sheet에 기록하기 위한 리스트 형태로 변환"""
        return [
            self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.strategy_name,
            self.order_type.value,
            self.ticker,
            self.executed_volume,
            self.executed_price,
            self.executed_amount,
        ]

    @staticmethod
    def from_result(result: ExecutionResult) -> "TradeRecord":
        return TradeRecord(
            strategy_name=result.strategy_name,
            order_type=result.order_type,
            ticker=result.ticker,
            executed_volume=result.executed_volume,
            executed_price=result.executed_price,
            executed_amount=result.executed_amount,
        )
