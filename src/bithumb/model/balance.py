"""빗썸 잔고 정보 모델"""

from dataclasses import dataclass
from typing import Any


@dataclass
class BalanceInfo:
    """빗썸 잔고 정보"""

    currency: str  # 통화 코드 (예: "BTC", "ETH", "KRW")
    balance: float  # 사용 가능 수량
    locked: float  # 거래 중 잠긴 수량
    avg_buy_price: float  # 평균 매수가
    avg_buy_price_modified: bool  # 평균 매수가 수정 여부
    unit_currency: str  # 기준 통화 (예: "KRW")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalanceInfo":
        """딕셔너리로부터 BalanceInfo 인스턴스를 생성합니다."""
        return cls(
            currency=data["currency"],
            balance=float(data["balance"]),
            locked=float(data["locked"]),
            avg_buy_price=float(data["avg_buy_price"]),
            avg_buy_price_modified=data["avg_buy_price_modified"],
            unit_currency=data["unit_currency"],
        )
