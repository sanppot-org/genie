"""해외 일/주/월/년 캔들 조회용 자산 유형 코드"""
from enum import Enum


class OverseasAssetType(str, Enum):
    """해외 캔들 데이터 조회 시 사용되는 자산 유형 코드
    
    inquire-daily-chartprice API의 FID_COND_MRKT_DIV_CODE 파라미터에 사용
    
    Attributes:
        INDEX: 해외지수
        EXCHANGE: 환율
        BOND: 국채
        GOLD: 금선물
    """
    INDEX = "N"  # 해외지수
    EXCHANGE = "X"  # 환율
    BOND = "I"  # 국채
    GOLD = "S"  # 금선물
