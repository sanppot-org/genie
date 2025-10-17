"""데이터 모델

전략에서 사용하는 캔들 데이터 모델을 정의합니다.
"""

import datetime
from enum import Enum
from functools import total_ordering

from pydantic import BaseModel, Field, model_validator


class Period(str, Enum):
    """반일봉 기간"""

    MORNING = "morning"
    AFTERNOON = "afternoon"


@total_ordering
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
    period: Period = Field(..., description="기간 (오전 or 오후)")
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

        최소: 0
        최대: 무한

        Returns:
            변동성

        Raises:
            ValueError: 시가가 0 이하일 때
        """
        if self.open <= 0.0:
            raise ValueError("시가가 0 이하입니다")
        return self.range / self.open

    @property
    def noise(self) -> float:
        """
        노이즈 비율 (1 - |시가 - 종가| / (고가 - 저가))

        캔들에서 꼬리가 차지하는 비율을 나타냅니다.
        꼬리가 클수록 노이즈가 커집니다.

        Returns:
            노이즈 비율 (레인지가 0이면 0 반환)
        """
        if self.range == 0.0:
            return 0.0
        return 1 - abs(self.open - self.close) / self.range

    @property
    def return_rate(self) -> float:
        """
        수익률 ((종가 - 시가) / 시가)

        Returns:
            수익률

        Raises:
            ValueError: 시가가 0 이하일 때
        """
        if self.open <= 0.0:
            raise ValueError("시가가 0 이하입니다")
        return (self.close - self.open) / self.open

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
            "volume": self.volume,
        }

    def __lt__(self, other: "HalfDayCandle") -> bool:
        """
        정렬을 위한 비교 연산자 (<)

        날짜 → 기간(오전 < 오후) 순서로 정렬됩니다.
        동등성 비교(__eq__)는 Pydantic의 기본 동작(모든 필드 비교)을 사용합니다.

        Args:
            other: 비교할 다른 HalfDayCandle 인스턴스

        Returns:
            self가 other보다 작으면 True
        """
        if self.date != other.date:
            return self.date < other.date
        # 같은 날짜면 오전이 오후보다 작음
        return self.period == Period.MORNING and other.period == Period.AFTERNOON


class Recent20DaysHalfDayCandles(BaseModel):
    """
    최근 20일의 반일봉 데이터 컬렉션

    최근 20일의 반일봉 데이터(총 40개: 오전 20개, 오후 20개)를 래핑하여
    변동성 돌파 전략 등에서 사용할 수 있는 메서드를 제공합니다.

    Attributes:
        candles: 최근 20일의 반일봉 데이터 리스트 (총 40개)
                - 오전 캔들 20개, 오후 캔들 20개
                - 입력 순서와 무관하게 자동으로 시간순 정렬됨
    """

    candles: list[HalfDayCandle] = Field(..., description="최근 20일의 반일봉 데이터 (40개)")

    @model_validator(mode="after")
    def validate_and_sort(self) -> "Recent20DaysHalfDayCandles":
        """
        캔들 개수 검증 및 시간순 정렬

        Returns:
            검증 및 정렬된 인스턴스

        Raises:
            ValueError: 캔들 개수가 40개가 아닐 때
        """
        if len(self.candles) != 40:
            raise ValueError(f"Expected 40 candles, got {len(self.candles)}")

        # HalfDayCandle의 __lt__ 메서드를 사용하여 시간순 정렬
        self.candles = sorted(self.candles)
        return self

    @property
    def morning_candles(self) -> list[HalfDayCandle]:
        """오전 캔들만 필터링"""
        return [c for c in self.candles if c.period == Period.MORNING]

    @property
    def afternoon_candles(self) -> list[HalfDayCandle]:
        """오후 캔들만 필터링"""
        return [c for c in self.candles if c.period == Period.AFTERNOON]

    @property
    def yesterday_morning(self) -> HalfDayCandle:
        """전일 오전 캔들 (가장 최근 오전)"""
        return self.morning_candles[-1]

    @property
    def yesterday_afternoon(self) -> HalfDayCandle:
        """전일 오후 캔들 (가장 최근 오후)"""
        return self.afternoon_candles[-1]

    def calculate_morning_noise_average(self) -> float:
        """
        최근 20일간 오전 노이즈의 평균 계산

        Returns:
            오전 노이즈 평균값
        """
        morning = self.morning_candles

        noise_sum = sum(candle.noise for candle in morning)

        return noise_sum / len(morning)

    def calculate_ma_score(self) -> float:
        """
        3,5,10,20일 오전 이동평균선 스코어 계산

        각 이평선이 전일 오전 종가보다 큰지 확인하여
        조건을 만족하는 이평선 개수를 4로 나눈 값을 반환합니다.

        최소: 0
        최대: 1

        Returns:
            이평선 스코어 (0.0 ~ 1.0)
        """
        morning = self.morning_candles
        yesterday_morning_close = self.yesterday_morning.close

        # 각 기간별 이동평균 계산
        periods = [3, 5, 10, 20]
        count = 0

        for period in periods:
            # 최근 N일간 오전 종가 평균
            recent_closes = [c.close for c in morning[-period:]]
            ma = sum(recent_closes) / len(recent_closes)

            # 이평선이 전일 오전 종가보다 크면 카운트
            if ma > yesterday_morning_close:
                count += 1

        return count / 4.0
