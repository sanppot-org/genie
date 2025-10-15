"""데이터 수집기

60분봉 캔들 데이터를 수집하고 오전/오후 반일봉으로 집계합니다.
"""

import datetime as dt
from datetime import datetime

import pandas as pd
from pandera.typing import DataFrame, Series

import constants
from src.strategy.data.models import HalfDayCandle, Period
from src.upbit import upbit_api
from src.upbit.model.candle import CandleSchema


class DataCollector:
    """
    캔들 데이터 수집 및 집계

    60분봉 캔들 데이터를 수집하고 오전(00:00-11:59) / 오후(12:00-23:59)
    반일봉으로 집계합니다.
    """

    def collect_data(self, ticker: str, days: int = 20) -> list[HalfDayCandle]:
        """
        초기 데이터 수집

        21일치 시간봉을 가져와서 타임스탬프 기준으로 정확히 지정된 일수만 필터링합니다.
        여유분은 스케줄러 지연, API 응답 시간, 봉 누락에 대응하기 위함입니다.

        Args:
            ticker: 티커 코드
            days: 수집할 일수 (기본값: 20)

        Returns:
            반일봉 리스트 (일수 * 2개)
        """
        # 여유분 포함하여 데이터 수집
        df = upbit_api.get_candles(
            ticker=ticker,
            interval=upbit_api.CandleInterval.MINUTE_60,
            count=(days + 1) * 24
        )

        return self._aggregate_all(df, days)

    def _aggregate_all(
            self,
            df: DataFrame[CandleSchema],
            days: int
    ) -> list[HalfDayCandle]:
        """
        어제부터 지정된 일수만큼 시간봉을 반일봉으로 집계

        오늘 데이터는 불완전하므로 제외하고, 어제부터 과거로 days만큼의
        날짜 데이터를 반일봉으로 집계합니다.

        Args:
            df: 시간봉 DataFrame
            days: 집계할 일수 (어제부터)

        Returns:
            반일봉 리스트 (days * 2개)
        """
        if df.empty:
            return []

        # 오늘 날짜 계산
        today = datetime.now().date()

        # DataFrame에서 고유한 날짜들 추출 (순서와 무관) 오늘 데이터 제외
        dates = pd.Series([idx.date() for idx in df.index if idx.date() < today])
        unique_dates = sorted(dates.unique())  # 최신순 정렬

        # 지정된 일수만큼만 처리 (어제부터)
        target_dates = unique_dates[:days]

        result = []
        for date in target_dates:
            # 집계
            morning, afternoon = self._aggregate_day(df, date)
            result.extend([morning, afternoon])

        return result

    def _aggregate_day(
            self,
            df: DataFrame[CandleSchema],
            date: dt.date
    ) -> tuple[HalfDayCandle, HalfDayCandle]:
        """
        전체 시간봉에서 특정 날짜 데이터를 추출하여 오전/오후 반일봉으로 집계

        Args:
            df: 전체 시간봉 DataFrame
            date: 집계할 날짜

        Returns:
            (오전 반일봉, 오후 반일봉) 튜플
        """
        # 해당 날짜의 데이터만 필터링
        date_df = df[df.index.date == date]

        # 오전(0-11시) / 오후(12-23시) 분리
        morning_df = date_df[date_df.index.hour < 12]
        afternoon_df = date_df[date_df.index.hour >= 12]

        # 집계
        morning = self._aggregate(morning_df, date, Period.MORNING)
        afternoon = self._aggregate(afternoon_df, date, Period.AFTERNOON)

        return morning, afternoon

    @staticmethod
    def _aggregate(
            hourly_df: Series[CandleSchema],
            date: dt.date,
            period: Period
    ) -> HalfDayCandle:
        """
        12개 시간봉을 하나의 반일봉으로 집계

        Args:
            hourly_df: 12개의 시간봉 Series[CandleSchema]
            date: 날짜
            period: 기간 ("morning" 또는 "afternoon")

        Returns:
            집계된 반일봉
        """
        return HalfDayCandle(
            date=date,
            period=period,
            open=hourly_df[constants.FIELD_OPEN].iloc[0],
            high=hourly_df[constants.FIELD_HIGH].max(),
            low=hourly_df[constants.FIELD_LOW].min(),
            close=hourly_df[constants.FIELD_CLOSE].iloc[-1],
            volume=hourly_df[constants.FIELD_VOLUME].sum()
        )
