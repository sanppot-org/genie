"""DataCollector 테스트"""

import datetime
from datetime import timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from src.strategy.data.collector import DataCollector
from src.strategy.data.models import Period
from src.upbit.upbit_api import CandleInterval


class TestDataCollector:
    """DataCollector 클래스 테스트"""

    @pytest.fixture
    def collector(self):
        """DataCollector 인스턴스 생성"""
        return DataCollector()

    @pytest.fixture
    def mock_hourly_df(self):
        """24개의 시간봉 Mock DataFrame 생성 (하루치)"""
        base_time = datetime.datetime(2025, 10, 13, 0, 0, 0)

        data = []
        index = []
        for i in range(24):
            data.append({
                'open': 50000.0 + i * 100,
                'high': 51000.0 + i * 100,
                'low': 49000.0 + i * 100,
                'close': 50500.0 + i * 100,
                'volume': 100.0 + i,
                'value': 5000000.0 + i * 10000
            })
            index.append(base_time + timedelta(hours=i))

        return pd.DataFrame(data, index=index)

    def test_aggregate_morning_candles(self, collector, mock_hourly_df):
        """오전 12시간 집계 테스트"""
        morning_df = mock_hourly_df.iloc[:12]
        result = collector._aggregate(morning_df, datetime.date(2025, 10, 13), Period.MORNING)

        assert result.date == datetime.date(2025, 10, 13)
        assert result.period == Period.MORNING
        assert result.open == 50000.0  # 첫 번째 캔들의 시가
        assert result.close == 51600.0  # 12번째 캔들의 종가 (50500 + 11*100)
        assert result.high == 52100.0  # 최고가 (51000 + 11*100)
        assert result.low == 49000.0  # 최저가
        assert result.volume == pytest.approx(1266.0)  # sum(100 + i for i in range(12))

    def test_aggregate_afternoon_candles(self, collector, mock_hourly_df):
        """오후 12시간 집계 테스트"""
        afternoon_df = mock_hourly_df.iloc[12:24]
        result = collector._aggregate(afternoon_df, datetime.date(2025, 10, 13), Period.AFTERNOON)

        assert result.date == datetime.date(2025, 10, 13)
        assert result.period == Period.AFTERNOON
        assert result.open == 51200.0  # 13번째 캔들의 시가 (50000 + 12*100)
        assert result.close == 52800.0  # 24번째 캔들의 종가 (50500 + 23*100)

    @patch('src.strategy.data.collector.upbit_api.get_candles')
    def test_collect_daily_data(self, mock_get_candles, collector):
        """어제 데이터 수집 테스트"""
        # 어제 날짜로 Mock 데이터 생성 (48시간치)
        yesterday = datetime.datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        data = []
        index = []
        for i in range(48):
            data.append({
                'open': 50000.0 + i * 100,
                'high': 51000.0 + i * 100,
                'low': 49000.0 + i * 100,
                'close': 50500.0 + i * 100,
                'volume': 100.0 + i,
                'value': 5000000.0 + i * 10000
            })
            index.append(yesterday_start + timedelta(hours=i))

        mock_df = pd.DataFrame(data, index=index)
        mock_get_candles.return_value = mock_df

        # 실행
        morning, afternoon = collector.collect_daily_data("KRW-BTC")

        # 검증
        mock_get_candles.assert_called_once_with(
            ticker="KRW-BTC",
            interval=CandleInterval.MINUTE_60,
            count=48
        )

        assert morning.date == yesterday.date()
        assert morning.period == Period.MORNING
        assert afternoon.date == yesterday.date()
        assert afternoon.period == Period.AFTERNOON

    @patch('src.strategy.data.collector.upbit_api.get_candles')
    def test_collect_initial_data(self, mock_get_candles, collector):
        """초기 20일치 데이터 수집 테스트"""
        # 어제부터 21일 전까지 시간봉 생성 (504개)
        data = []
        index = []
        yesterday = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        for day in range(21):
            base_time = yesterday - timedelta(days=day)
            for hour in range(24):
                data.append({
                    'open': 50000.0 + day * 1000,
                    'high': 51000.0 + day * 1000,
                    'low': 49000.0 + day * 1000,
                    'close': 50500.0 + day * 1000,
                    'volume': 100.0,
                    'value': 5000000.0
                })
                index.append(base_time + timedelta(hours=hour))

        mock_get_candles.return_value = pd.DataFrame(data, index=index)

        # 실행
        result = collector.collect_initial_data("KRW-BTC", days=20)

        # 검증
        mock_get_candles.assert_called_once_with(
            ticker="KRW-BTC",
            interval=CandleInterval.MINUTE_60,
            count=504  # 21일 * 24시간
        )

        # 20일 * 2(오전/오후) = 40개의 반일봉
        assert len(result) == 40

        # 첫 번째와 마지막 캔들 확인
        assert result[0].period == Period.MORNING
        assert result[1].period == Period.AFTERNOON
        assert result[-2].period == Period.MORNING
        assert result[-1].period == Period.AFTERNOON

    @patch('src.strategy.data.collector.upbit_api.get_candles')
    def test_collect_initial_data_filters_by_timestamp(self, mock_get_candles, collector):
        """타임스탬프 기준으로 정확히 20일치만 추출하는지 테스트"""
        # 어제부터 넉넉하게 25일치 생성
        data = []
        index = []
        yesterday = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        for day in range(25):
            base_time = yesterday - timedelta(days=day)
            for hour in range(24):
                data.append({
                    'open': 50000.0,
                    'high': 51000.0,
                    'low': 49000.0,
                    'close': 50500.0,
                    'volume': 100.0,
                    'value': 5000000.0
                })
                index.append(base_time + timedelta(hours=hour))

        mock_get_candles.return_value = pd.DataFrame(data, index=index)

        # 실행
        result = collector.collect_initial_data("KRW-BTC", days=20)

        # 타임스탬프 필터링 후 정확히 40개 (20일 * 2)
        assert len(result) == 40

    def test_aggregate_all(self, collector):
        """전체 기간 집계 테스트"""
        # 2일치 시간봉 생성 (48개)
        data = []
        index = []
        base_time = datetime.datetime(2025, 10, 1, 0, 0, 0)
        for day in range(2):
            for hour in range(24):
                data.append({
                    'open': 50000.0 + day * 1000,
                    'high': 51000.0 + day * 1000,
                    'low': 49000.0 + day * 1000,
                    'close': 50500.0 + day * 1000,
                    'volume': 100.0,
                    'value': 5000000.0
                })
                index.append(base_time + timedelta(days=day, hours=hour))

        df = pd.DataFrame(data, index=index)
        result = collector._aggregate_all(df, days=2)

        # 2일 * 2(오전/오후) = 4개
        assert len(result) == 4
        assert result[0].period == Period.MORNING
        assert result[1].period == Period.AFTERNOON
        assert result[2].period == Period.MORNING
        assert result[3].period == Period.AFTERNOON

    def test_aggregate_all_excludes_today(self, collector):
        """오늘 날짜 제외 테스트"""
        # 오늘, 어제, 그제 3일치 시간봉 생성 (72개)
        data = []
        index = []
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for day_offset in range(3):  # 0(오늘), 1(어제), 2(그제)
            base_time = today - timedelta(days=day_offset)
            for hour in range(24):
                data.append({
                    'open': 50000.0 + day_offset * 1000,
                    'high': 51000.0 + day_offset * 1000,
                    'low': 49000.0 + day_offset * 1000,
                    'close': 50500.0 + day_offset * 1000,
                    'volume': 100.0,
                    'value': 5000000.0
                })
                index.append(base_time + timedelta(hours=hour))

        df = pd.DataFrame(data, index=index)

        # 2일치 요청 (어제, 그제만 포함되어야 함)
        result = collector._aggregate_all(df, days=2)

        # 2일 * 2(오전/오후) = 4개
        assert len(result) == 4

        # 오늘 날짜가 결과에 포함되지 않았는지 확인
        today_date = datetime.datetime.now().date()
        for half_day in result:
            assert half_day.date < today_date, "오늘 날짜가 결과에 포함되면 안 됨"

        # 어제와 그제만 포함되었는지 확인
        yesterday = (datetime.datetime.now() - timedelta(days=1)).date()
        day_before_yesterday = (datetime.datetime.now() - timedelta(days=2)).date()

        result_dates = set([half_day.date for half_day in result])
        assert result_dates == {yesterday, day_before_yesterday}
