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

class TimeInForce(Enum):
    IOC = "ioc"
    FOK = "fok"
    POST_ONLY = "post_only"

from pydantic import BaseModel, field_validator


class OrderParams(BaseModel):
    """
    주문 요청 파라미터

    주문 생성 시 사용되는 파라미터를 검증합니다.

    Attributes:
        market: 마켓 ID (필수, 예: "KRW-BTC")
        side: 주문 방향 (필수, "bid": 매수, "ask": 매도)
        ord_type: 주문 타입 (필수, "limit": 지정가, "price": 시장가 매수, "market": 시장가 매도, "best": 최유리지정가)
        volume: 주문량 (선택, 지정가/시장가 매도/최유리지정가 매도 시 필수, 양수 float)
        price: 주문 가격/금액 (선택, 지정가/시장가 매수/최유리지정가 매수 시 필수, 양수 float)
        time_in_force: 주문 실행 조건 (선택, 최유리지정가 주문 시 필수)
    """

    market: str
    side: OrderSide
    ord_type: OrderType
    volume: float | None = None
    price: float | None = None
    time_in_force: TimeInForce | None = None

    @field_validator("market")
    @classmethod
    def validate_market(cls, v: str) -> str:
        """마켓 ID는 비어있지 않아야 한다"""
        if not v or not v.strip():
            raise ValueError("market은 비어있을 수 없습니다")
        return v

    @field_validator("volume", "price")
    @classmethod
    def validate_positive_number(cls, v: float | None) -> float | None:
        """volume과 price는 양수여야 한다"""
        if v is not None and v <= 0:
            raise ValueError("양수여야 합니다")
        return v

    def model_post_init(self, __context: Any) -> None:
        """ord_type에 따른 필수 파라미터 검증"""
        # 지정가 주문: price와 volume 필수
        if self.ord_type == OrderType.LIMIT:
            if self.price is None:
                raise ValueError("지정가 주문에는 price가 필요합니다")
            if self.volume is None:
                raise ValueError("지정가 주문에는 volume이 필요합니다")

        # 시장가 매수(price): price 필수
        elif self.ord_type == OrderType.PRICE:
            if self.price is None:
                raise ValueError("시장가 매수에는 price가 필요합니다")

        # 시장가 매도(market): volume 필수
        elif self.ord_type == OrderType.MARKET:
            if self.volume is None:
                raise ValueError("시장가 매도에는 volume이 필요합니다")

        # 최유리지정가(best): time_in_force 필수 (ioc 또는 fok만 허용)
        elif self.ord_type == OrderType.BEST:
            # time_in_force 필수
            if self.time_in_force is None:
                raise ValueError("최유리지정가 주문에는 time_in_force가 필요합니다")
            
            # ioc 또는 fok만 허용
            if self.time_in_force not in [TimeInForce.IOC, TimeInForce.FOK]:
                raise ValueError("최유리지정가 주문은 time_in_force를 ioc 또는 fok로 설정해야 합니다")
            
            # 매수(bid): price 필수
            if self.side == OrderSide.BID:
                if self.price is None:
                    raise ValueError("최유리지정가 매수에는 price가 필요합니다")
            
            # 매도(ask): volume 필수
            elif self.side == OrderSide.ASK:
                if self.volume is None:
                    raise ValueError("최유리지정가 매도에는 volume이 필요합니다")

    def to_dict(self) -> dict[str, str]:
        """
        API 요청용 딕셔너리로 변환

        None 값은 제외하고, Enum 값은 value로 변환하며, float는 문자열로 변환합니다.

        Returns:
            API 요청에 사용할 딕셔너리
        """
        result: dict[str, str] = {
            "market": self.market,
            "side": self.side.value,
            "ord_type": self.ord_type.value,
        }

        if self.volume is not None:
            result["volume"] = str(self.volume)

        if self.price is not None:
            result["price"] = str(self.price)

        if self.time_in_force is not None:
            result["time_in_force"] = self.time_in_force.value

        return result


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
