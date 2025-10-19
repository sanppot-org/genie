"""데이터 수집기

60분봉 캔들 데이터를 수집하고 오전/오후 반일봉으로 집계합니다.
"""

import datetime as dt
import logging

import pandas as pd
from pandera.typing import DataFrame, Series

from src import constants
from src.strategy.cache_manager import CacheManager
from src.strategy.cache_models import DataCache
from src.strategy.clock import Clock
from src.strategy.data.models import HalfDayCandle, Period, Recent20DaysHalfDayCandles
from src.upbit import upbit_api
from src.upbit.model.candle import CandleSchema
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


class DataCollector:
    """
    캔들 데이터 수집 및 집계

    60분봉 캔들 데이터를 수집하고 오전(00:00-11:59) / 오후(12:00-23:59)
    반일봉으로 집계합니다.

    캐싱 전략:
    - 파일 캐시: 영구 보존, 프로세스 재시작 후에도 유지
    - 날짜별로 캐시 파일 관리 (last_update_date로 구분)
    """

    def __init__(self, clock: Clock, cache_manager: CacheManager | None = None) -> None:
        """DataCollector 초기화

        Args:
            clock: 시간 제공자
            cache_manager: 파일 캐시 관리자 (None이면 기본 생성)
        """
        self._clock = clock
        self._cache_manager = cache_manager or CacheManager(file_suffix="data")

    def collect_data(self, ticker: str, days: int = 20) -> Recent20DaysHalfDayCandles:
        """
        초기 데이터 수집

        21일치 시간봉을 가져와서 타임스탬프 기준으로 정확히 지정된 일수만 필터링합니다.
        여유분은 스케줄러 지연, API 응답 시간, 봉 누락에 대응하기 위함입니다.

        캐싱 전략:
        1. 파일 캐시 확인
        2. API 호출 → 파일 캐시에 저장
        - 같은 날짜, 같은 티커로 요청하면 캐시된 데이터 반환
        - 날짜가 바뀌면 자동으로 새 캐시 파일 생성

        Args:
            ticker: 티커 코드
            days: 수집할 일수 (기본값: 20)

        Returns:
            Recent20DaysHalfDayCandles 객체 (20일 * 2 = 40개 캔들)
        """
        today = self._clock.today()

        # 파일 캐시 확인
        file_cache = self._cache_manager.load_data_cache(ticker)
        if file_cache and file_cache.last_update_date == today:
            logger.debug(f"파일 캐시 히트: {ticker}, {today}")
            return file_cache.history

        logger.debug(f"파일 캐시 미스: {ticker}, {today}")

        # API 호출
        df = UpbitAPI.get_candles(ticker=ticker, interval=upbit_api.CandleInterval.MINUTE_60, count=(days + 1) * 24)

        candles = self._aggregate_all(df, days)
        result = Recent20DaysHalfDayCandles(candles=candles)

        # 파일 캐시 저장
        data_cache = DataCache(ticker=ticker, last_update_date=today, history=result)
        self._cache_manager.save_data_cache(ticker, data_cache)

        return result

    def _aggregate_all(self, df: DataFrame[CandleSchema], days: int) -> list[HalfDayCandle]:
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
        today = self._clock.today()

        # DataFrame에서 고유한 날짜들 추출 (순서와 무관) 오늘 데이터 제외
        dates = pd.Series([idx.date() for idx in df.index if idx.date() < today])
        unique_dates = sorted(dates.unique())  # 오름차순 정렬 (오래된 것 → 최신)

        # 지정된 일수만큼만 처리 (최근 n일)
        target_dates = unique_dates[-days:] if len(unique_dates) >= days else unique_dates

        result = []
        for target_date in target_dates:
            # 집계
            morning, afternoon = self._aggregate_day(df, target_date)
            result.extend([morning, afternoon])

        return result

    def _aggregate_day(self, df: DataFrame[CandleSchema], target_date: dt.date) -> tuple[HalfDayCandle, HalfDayCandle]:
        """
        전체 시간봉에서 특정 날짜 데이터를 추출하여 오전/오후 반일봉으로 집계

        Args:
            df: 전체 시간봉 DataFrame
            target_date: 집계할 날짜

        Returns:
            (오전 반일봉, 오후 반일봉) 튜플
        """
        # 해당 날짜의 데이터만 필터링
        date_df = df[df.index.normalize() == pd.Timestamp(target_date)]

        # 오전(0-11시) / 오후(12-23시) 분리
        morning_df = date_df[date_df.index.hour < 12]
        afternoon_df = date_df[date_df.index.hour >= 12]

        # 집계
        morning = self._aggregate(morning_df, target_date, Period.MORNING)
        afternoon = self._aggregate(afternoon_df, target_date, Period.AFTERNOON)

        return morning, afternoon

    @staticmethod
    def _aggregate(hourly_df: Series[CandleSchema], target_date: dt.date, period: Period) -> HalfDayCandle:
        """
        12개 시간봉을 하나의 반일봉으로 집계

        Args:
            hourly_df: 12개의 시간봉 Series[CandleSchema]
            target_date: 날짜
            period: 기간 ("morning" 또는 "afternoon")

        Returns:
            집계된 반일봉
        """
        return HalfDayCandle(
            date=target_date,
            period=period,
            open=hourly_df[constants.FIELD_OPEN].iloc[0],
            high=hourly_df[constants.FIELD_HIGH].max(),
            low=hourly_df[constants.FIELD_LOW].min(),
            close=hourly_df[constants.FIELD_CLOSE].iloc[-1],
            volume=hourly_df[constants.FIELD_VOLUME].sum(),
        )
