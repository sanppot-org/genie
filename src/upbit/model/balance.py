from dataclasses import dataclass
from typing import Any


@dataclass
class BalanceInfo:
    """
    업비트 잔고 정보

    계좌의 자산 잔고를 나타냅니다. 모든 숫자 필드는 정밀도 보존을 위해 문자열로 제공됩니다.

    Attributes:
        currency: 통화 코드 (예: "BTC", "ETH", "KRW")
        balance: 사용 가능 수량 (문자열)
        locked: 거래 중 잠긴 수량 (문자열)
        avg_buy_price: 평균 매수가 (문자열)
        avg_buy_price_modified: 평균 매수가 수정 여부
        unit_currency: 기준 통화 (예: "KRW")
    """

    currency: str
    balance: float
    locked: float
    avg_buy_price: float
    avg_buy_price_modified: bool
    unit_currency: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalanceInfo":
        """
        딕셔너리로부터 BalanceInfo 인스턴스를 생성합니다.

        Args:
            data: 업비트 API 응답 딕셔너리

        Returns:
            BalanceInfo 인스턴스
        """
        return cls(
            currency=data["currency"],
            balance=float(data["balance"]),
            locked=float(data["locked"]),
            avg_buy_price=float(data["avg_buy_price"]),
            avg_buy_price_modified=data["avg_buy_price_modified"],
            unit_currency=data["unit_currency"],
        )
