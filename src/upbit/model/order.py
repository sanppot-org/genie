from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


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
class Trade:
    """
    개별 체결 내역

    Attributes:
        market: 마켓 ID (예: "KRW-ETH")
        uuid: 체결 고유 ID
        price: 체결 가격 (문자열)
        volume: 체결량 (문자열)
        funds: 체결 금액 (문자열)
        trend: 체결 트렌드 ("up": 상승, "down": 하락)
        created_at: 체결 시간 (ISO 8601 형식)
        side: 체결 방향 ("bid": 매수, "ask": 매도)
    """

    market: str
    uuid: str
    price: float
    volume: float
    funds: float
    trend: str
    created_at: datetime
    side: OrderSide

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trade":
        """
        딕셔너리로부터 Trade 인스턴스를 생성합니다.

        Args:
            data: 업비트 API 응답 딕셔너리

        Returns:
            Trade 인스턴스
        """
        return cls(
            market=data["market"],
            uuid=data["uuid"],
            price=float(data["price"]),
            volume=float(data["volume"]),
            funds=float(data["funds"]),
            trend=data["trend"],
            created_at=datetime.fromisoformat(data["created_at"]),
            side=OrderSide(data["side"]),
        )


@dataclass
class OrderResult:
    """
    업비트 주문 결과

    주문 생성/조회 결과를 나타냅니다. API 응답의 숫자 문자열은 적절한 타입(float/int)으로 변환됩니다.

    Attributes:
        uuid: 주문 고유 ID
        side: 주문 방향 ("bid": 매수, "ask": 매도)
        ord_type: 주문 타입 ("limit": 지정가, "price": 시장가 매수, "market": 시장가 매도)
        price: 주문 가격/금액 (float, 시장가 매도의 경우 None)
        state: 주문 상태 ("wait": 대기, "watch": 예약, "done": 완료, "cancel": 취소)
        market: 마켓 ID (예: "KRW-BTC", "KRW-ETH")
        created_at: 주문 생성 시간 (ISO 8601 형식)
        volume: 주문량 (float, 시장가 매수의 경우 None)
        remaining_volume: 남은 주문량 (float, 매수의 경우 None)
        executed_volume: 체결된 양 (float)
        reserved_fee: 예약된 수수료 (float)
        remaining_fee: 남은 수수료 (float)
        paid_fee: 지불된 수수료 (float)
        locked: 잠긴 금액 (float)
        trades_count: 체결 건수 (int)
        trades: 체결 내역 리스트
    """

    uuid: str
    side: OrderSide
    ord_type: OrderType
    price: float | None
    state: OrderState
    market: str
    created_at: datetime
    volume: float | None
    remaining_volume: float | None  # 매수의 경우 없다.
    executed_volume: float
    reserved_fee: float
    remaining_fee: float
    paid_fee: float
    locked: float
    trades_count: int
    trades: list[Trade]

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
            uuid=data["uuid"],
            side=OrderSide(data["side"]),
            ord_type=OrderType(data["ord_type"]),
            price=float(data["price"]) if data.get("price") else None,
            state=OrderState(data["state"]),
            market=data["market"],
            created_at=datetime.fromisoformat(data["created_at"]),
            volume=float(data["volume"]) if data.get("volume") else None,
            remaining_volume=float(data["remaining_volume"]) if data.get("remaining_volume") else None,
            executed_volume=float(data["executed_volume"]),
            reserved_fee=float(data["reserved_fee"]),
            remaining_fee=float(data["remaining_fee"]),
            paid_fee=float(data["paid_fee"]),
            locked=float(data["locked"]),
            trades_count=int(data["trades_count"]),
            trades=[Trade.from_dict(trade) for trade in data.get("trades", [])],
        )
