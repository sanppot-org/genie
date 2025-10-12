"""해외 캔들 데이터 조회용 기간 구분 코드"""
from enum import Enum


class OverseasCandlePeriod(str, Enum):
    """해외 캔들 데이터 조회 시 사용되는 기간 구분 코드
    
    inquire-daily-chartprice API의 FID_PERIOD_DIV_CODE 파라미터에 사용
    
    Attributes:
        DAILY: 일봉
        WEEKLY: 주봉
        MONTHLY: 월봉
        YEARLY: 연봉
    """
    DAILY = "D"  # 일봉
    WEEKLY = "W"  # 주봉
    MONTHLY = "M"  # 월봉
    YEARLY = "Y"  # 연봉
