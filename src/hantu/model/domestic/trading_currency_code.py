"""거래 통화 코드 정의"""

from enum import Enum


class TradingCurrencyCode(str, Enum):
    """거래 통화 코드

    한국투자증권 해외 주식 API에서 사용하는 거래 통화 코드

    Attributes:
        USD: 미국 달러
        HKD: 홍콩 달러
        CNY: 중국 위안화
        JPY: 일본 엔화
        VND: 베트남 동
    """

    USD = "USD"  # 미국 달러
    HKD = "HKD"  # 홍콩 달러
    CNY = "CNY"  # 중국 위안화
    JPY = "JPY"  # 일본 엔화
    VND = "VND"  # 베트남 동
