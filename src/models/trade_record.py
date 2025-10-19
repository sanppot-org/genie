"""거래 기록 모델"""

from pydantic import BaseModel


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

    timestamp: str
    strategy_name: str
    order_type: str
    ticker: str
    executed_volume: float
    executed_price: float
    executed_amount: float

    def to_list(self) -> list:
        """Google Sheet에 기록하기 위한 리스트 형태로 변환"""
        return [
            self.timestamp,
            self.strategy_name,
            self.order_type,
            self.ticker,
            self.executed_volume,
            self.executed_price,
            self.executed_amount,
        ]
