"""한국투자증권 계좌 타입 정의"""

from enum import Enum


class AccountType(str, Enum):
    """한국투자증권 계좌 타입

    Attributes:
        REAL: 실제 계좌
        VIRTUAL: 가상 계좌 (모의투자)
    """

    REAL = "real"
    VIRTUAL = "virtual"
