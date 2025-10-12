"""시장 구분 코드"""
from enum import Enum


class MarketCode(str, Enum):
    """시장 구분 코드

    한국투자증권 API에서 사용하는 시장 분류 코드
    """
    KRX = "J"  # 한국거래소 (코스피/코스닥)
    NXT = "NX"  # 넥스트레이드
    ALL = "UN"  # 통합
