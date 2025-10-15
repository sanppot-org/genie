"""데이터 모델

전략에서 사용하는 캔들 데이터 모델을 정의합니다.
"""

import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Period(str, Enum):
    """반일봉 기간"""
    MORNING = "morning"
    AFTERNOON = "afternoon"


class HalfDayCandle(BaseModel):
    """
    반일 캔들 데이터

    오전 또는 오후 12시간 동안의 OHLCV 데이터를 나타냅니다.

    Attributes:
        date: 날짜 (YYYY-MM-DD)
        period: 기간 ("morning" 또는 "afternoon")
        open: 시가
        high: 고가
        low: 저가
        close: 종가
        volume: 누적 거래량
    """

    date: datetime.date = Field(..., description="날짜 (YYYY-MM-DD)")
    period: Period = Field(..., description="기간")
    open: float = Field(..., description="시가")
    high: float = Field(..., description="고가")
    low: float = Field(..., description="저가")
    close: float = Field(..., description="종가")
    volume: float = Field(..., description="누적 거래량")

    @property
    def range(self) -> float:
        """
        가격 범위 (고가 - 저가)

        Returns:
            가격 범위
        """
        return self.high - self.low

    @property
    def volatility(self) -> float:
        """
        변동성 ((고가 - 저가) / 시가)

        Returns:
            변동성
        """
        if self.open == 0.0:
            return float('inf')
        return self.range / self.open

    @classmethod
    def from_dict(cls, data: dict) -> "HalfDayCandle":
        """
        딕셔너리로부터 HalfDayCandle 생성

        Args:
            data: 캔들 데이터 딕셔너리

        Returns:
            HalfDayCandle 인스턴스
        """
        return cls(**data)

    def to_dict(self) -> dict:
        """
        딕셔너리로 변환

        Returns:
            캔들 데이터 딕셔너리
        """
        return {
            "date": self.date.isoformat(),
            "period": self.period,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }
