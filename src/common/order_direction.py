from enum import Enum


class OrderDirection(str, Enum):
    """주문 방향"""

    BUY = "매수"
    SELL = "매도"
