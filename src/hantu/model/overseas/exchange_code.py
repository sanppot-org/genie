"""해외 거래소 코드 정의"""

from enum import Enum


class OverseasExchangeCode(str, Enum):
    """해외 거래소 코드

    한국투자증권 해외 주식 API에서 사용하는 거래소 코드

    Attributes:
        [모의]
        NASD : 나스닥
        NYSE : 뉴욕
        AMEX : 아멕스

        [실전]
        NASD: 미국 전체
        NAS: 나스닥
        NYSE: 뉴욕 증권거래소
        AMEX: 아메리칸 증권거래소

        [모의/실전 공통]
        SEHK: 홍콩 증권거래소
        SHAA: 중국 상해 증권거래소
        SZAA: 중국 심천 증권거래소
        TKSE: 일본 도쿄 증권거래소
        HASE: 베트남 하노이 증권거래소
        VNSE: 베트남 호치민 증권거래소
    """

    NASD = "NASD"  # 미국 전체
    NAS = "NAS"  # 나스닥
    NYSE = "NYSE"  # 뉴욕
    AMEX = "AMEX"  # 아멕스
    SEHK = "SEHK"  # 홍콩
    SHAA = "SHAA"  # 중국 상해
    SZAA = "SZAA"  # 중국 심천
    TKSE = "TKSE"  # 일본
    HASE = "HASE"  # 베트남 하노이
    VNSE = "VNSE"  # 베트남 호치민
