from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class OrderSide(Enum):
    BID = "bid"  # 매수
    ASK = "ask"  # 매도


class OrderType(Enum):
    LIMIT = "limit"  # 지정가
    MARKET = "market"  # 시장가 매도
    BEST = "best"  # 최유리 지정가 매수/매도
    PRICE = "price"  # 시장가 매수


class OrderState(Enum):
    WAIT = "wait"
    WATCH = "watch"
    DONE = "done"
    CANCEL = "cancel"


@dataclass
class OrderResult:
    """
    업비트 주문 결과

    주문 생성/조회 결과를 나타냅니다. 모든 숫자 필드는 정밀도 보존을 위해 문자열로 제공됩니다.

    Attributes:
        market: 마켓 ID (예: "KRW-BTC", "KRW-ETH")
        uuid: 주문 고유 ID
        side: 주문 방향 ("bid": 매수, "ask": 매도)
        ord_type: 주문 타입 ("limit": 지정가, "price": 시장가 매수, "market": 시장가 매도)
        price: 주문 가격/금액 (문자열)
        state: 주문 상태 ("wait": 대기, "watch": 예약, "done": 완료, "cancel": 취소)
        created_at: 주문 생성 시간 (ISO 8601 형식)
        volume: 주문량 (문자열)
        remaining_volume: 남은 주문량 (문자열)
        executed_volume: 체결된 양 (문자열)
        reserved_fee: 예약된 수수료 (문자열)
        remaining_fee: 남은 수수료 (문자열)
        paid_fee: 지불된 수수료 (문자열)
        locked: 잠긴 금액 (문자열)
        trades_count: 체결 건수
    """

    market: str
    uuid: str
    side: OrderSide
    ord_type: OrderType
    price: Optional[float]
    state: OrderState
    created_at: datetime
    volume: Optional[float]
    remaining_volume: Optional[float]  # 매수의 경우 없다.
    executed_volume: float
    reserved_fee: float
    remaining_fee: float
    paid_fee: float
    locked: float
    trades_count: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderResult":
        """
        딕셔너리로부터 OrderResult 인스턴스를 생성합니다.

        Args:
            data: 업비트 API 응답 딕셔너리

        Returns:
            OrderResult 인스턴스
        """
        return cls(
            market=data["market"],
            uuid=data["uuid"],
            side=OrderSide(data["side"]),
            ord_type=OrderType(data["ord_type"]),
            price=float(data["price"]) if data.get("price") else None,
            state=OrderState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            volume=float(data["volume"]) if data.get("volume") else None,
            remaining_volume=float(data["remaining_volume"]) if data.get("remaining_volume") else None,
            reserved_fee=float(data["reserved_fee"]),
            remaining_fee=float(data["remaining_fee"]),
            paid_fee=float(data["paid_fee"]),
            locked=float(data["locked"]),
            executed_volume=float(data["executed_volume"]),
            trades_count=float(data["trades_count"]),
        )
