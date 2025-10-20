"""해외 시세 조회용 거래소 코드 정의"""

from enum import Enum


class OverseasMarketCode(str, Enum):
    """해외주식 시세 조회 API용 거래소 코드

    price, price_detail, inquire_asking_price 등 시세 조회 API에서 사용
    잔고 조회나 주문 API에서 사용하는 OverseasExchangeCode와는 다른 코드 체계

    Attributes:
        HKS: 홍콩증권거래소
        NYS: 뉴욕증권거래소 (NYSE)
        NAS: 나스닥
        AMS: 아멕스 (AMEX)
        TSE: 도쿄증권거래소
        SHS: 상하이 A주
        SZS: 심천 A주
        SHI: 상하이 지수
        SZI: 심천 지수
        HSX: 호치민증권거래소
        HNX: 하노이증권거래소
        BAY: 베트남
        BAQ: 베트남
        BAA: 베트남
    """

    HKS = "HKS"  # 홍콩증권거래소
    NYS = "NYS"  # 뉴욕증권거래소 (NYSE)
    NAS = "NAS"  # 나스닥
    AMS = "AMS"  # 아멕스 (AMEX)
    TSE = "TSE"  # 도쿄증권거래소
    SHS = "SHS"  # 상하이 A주
    SZS = "SZS"  # 심천 A주
    SHI = "SHI"  # 상하이 지수
    SZI = "SZI"  # 심천 지수
    HSX = "HSX"  # 호치민증권거래소
    HNX = "HNX"  # 하노이증권거래소
    BAY = "BAY"  # 베트남
    BAQ = "BAQ"  # 베트남
    BAA = "BAA"  # 베트남
