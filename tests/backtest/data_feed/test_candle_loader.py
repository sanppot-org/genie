"""캔들 데이터 로더 테스트"""

from datetime import date, datetime

import pandas as pd

from src.backtest.data_feed.candle_loader import candles_to_dataframe, timeframe_to_korean
from src.database.models import CandleDaily, CandleHour1, CandleMinute1


class TestCandlesToDataframe:
    """candles_to_dataframe 함수 테스트"""

    def test_converts_candle_list_to_dataframe(self) -> None:
        """CandleDaily 리스트를 DataFrame으로 변환"""
        # Given: CandleDaily 리스트
        candles = [
            self._create_daily_candle(date(2024, 1, 1), 50000.0, 51000.0, 49000.0, 50500.0, 100.0),
            self._create_daily_candle(date(2024, 1, 2), 50500.0, 52000.0, 50000.0, 51500.0, 150.0),
        ]

        # When: DataFrame 변환
        df, timeframe = candles_to_dataframe(candles)

        # Then: DataFrame 구조 검증
        assert len(df) == 2
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert timeframe == "1d"

    def test_dataframe_has_datetime_index(self) -> None:
        """DataFrame의 인덱스가 DatetimeIndex인지 확인"""
        # Given
        candles = [
            self._create_daily_candle(date(2024, 1, 1), 50000.0, 51000.0, 49000.0, 50500.0, 100.0),
        ]

        # When
        df, timeframe = candles_to_dataframe(candles)

        # Then
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_dataframe_sorted_by_date(self) -> None:
        """DataFrame이 날짜순으로 정렬되어 있는지 확인"""
        # Given: 역순으로 정렬된 캔들
        candles = [
            self._create_daily_candle(date(2024, 1, 3), 52000.0, 53000.0, 51000.0, 52500.0, 200.0),
            self._create_daily_candle(date(2024, 1, 1), 50000.0, 51000.0, 49000.0, 50500.0, 100.0),
            self._create_daily_candle(date(2024, 1, 2), 50500.0, 52000.0, 50000.0, 51500.0, 150.0),
        ]

        # When
        df, timeframe = candles_to_dataframe(candles)

        # Then: 인덱스가 오름차순
        assert df.index[0] < df.index[1] < df.index[2]

    def test_dataframe_values_correct(self) -> None:
        """DataFrame의 값이 올바른지 확인"""
        # Given
        candle = self._create_daily_candle(date(2024, 1, 1), 50000.0, 51000.0, 49000.0, 50500.0, 100.0)
        candles = [candle]

        # When
        df, timeframe = candles_to_dataframe(candles)

        # Then
        assert df.iloc[0]['open'] == 50000.0
        assert df.iloc[0]['high'] == 51000.0
        assert df.iloc[0]['low'] == 49000.0
        assert df.iloc[0]['close'] == 50500.0
        assert df.iloc[0]['volume'] == 100.0

    def test_empty_list_returns_empty_dataframe(self) -> None:
        """빈 리스트가 주어지면 빈 DataFrame 반환"""
        # Given
        candles: list[CandleDaily] = []

        # When
        df, timeframe = candles_to_dataframe(candles)

        # Then
        assert len(df) == 0
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert timeframe == "unknown"

    def test_minute_candle_returns_1m_timeframe(self) -> None:
        """CandleMinute1은 1m 타임프레임 반환"""
        # Given
        candles = [
            self._create_minute_candle(datetime(2024, 1, 1, 9, 0), 50000.0, 51000.0, 49000.0, 50500.0, 100.0),
        ]

        # When
        df, timeframe = candles_to_dataframe(candles)

        # Then
        assert timeframe == "1m"

    def test_hour_candle_returns_1h_timeframe(self) -> None:
        """CandleHour1은 1h 타임프레임 반환"""
        # Given
        candles = [
            self._create_hour_candle(datetime(2024, 1, 1, 9, 0), 50000.0, 51000.0, 49000.0, 50500.0, 100.0),
        ]

        # When
        df, timeframe = candles_to_dataframe(candles)

        # Then
        assert timeframe == "1h"

    def _create_daily_candle(
            self,
            candle_date: date,
            open_price: float,
            high: float,
            low: float,
            close: float,
            volume: float,
    ) -> CandleDaily:
        """테스트용 CandleDaily 생성"""
        candle = CandleDaily()
        candle.date = candle_date
        candle.ticker_id = 1
        candle.open = open_price
        candle.high = high
        candle.low = low
        candle.close = close
        candle.volume = volume
        return candle

    def _create_minute_candle(
            self,
            kst_time: datetime,
            open_price: float,
            high: float,
            low: float,
            close: float,
            volume: float,
    ) -> CandleMinute1:
        """테스트용 CandleMinute1 생성"""
        candle = CandleMinute1()
        candle.kst_time = kst_time
        candle.timestamp = kst_time
        candle.ticker_id = 1
        candle.open = open_price
        candle.high = high
        candle.low = low
        candle.close = close
        candle.volume = volume
        return candle

    def _create_hour_candle(
            self,
            kst_time: datetime,
            open_price: float,
            high: float,
            low: float,
            close: float,
            volume: float,
    ) -> CandleHour1:
        """테스트용 CandleHour1 생성"""
        candle = CandleHour1()
        candle.kst_time = kst_time
        candle.ticker_id = 1
        candle.open = open_price
        candle.high = high
        candle.low = low
        candle.close = close
        candle.volume = volume
        return candle


class TestTimeframeToKorean:
    """timeframe_to_korean 함수 테스트"""

    def test_1m_to_korean(self) -> None:
        """1m → 1분봉"""
        assert timeframe_to_korean("1m") == "1분봉 (1 Minute)"

    def test_1h_to_korean(self) -> None:
        """1h → 1시간봉"""
        assert timeframe_to_korean("1h") == "1시간봉 (1 Hour)"

    def test_1d_to_korean(self) -> None:
        """1d → 일봉"""
        assert timeframe_to_korean("1d") == "일봉 (Daily)"

    def test_unknown_to_korean(self) -> None:
        """unknown → 알 수 없음"""
        assert timeframe_to_korean("unknown") == "알 수 없음"
