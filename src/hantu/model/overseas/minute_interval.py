"""해외주식 분봉 간격 코드"""
from enum import Enum


class OverseasMinuteInterval(str, Enum):
    """해외주식 분봉 간격 코드

    inquire-time-itemchartprice API의 NMIN 파라미터에 사용

    Attributes:
        MIN_1: 1분봉
        MIN_5: 5분봉
        MIN_10: 10분봉
        MIN_30: 30분봉
        MIN_60: 60분봉
    """
    MIN_1 = "1"  # 1분봉
    MIN_5 = "5"  # 5분봉
    MIN_10 = "10"  # 10분봉
    MIN_30 = "30"  # 30분봉
    MIN_60 = "60"  # 60분봉 (1시간)
