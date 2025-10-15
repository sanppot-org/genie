"""변동성 돌파 전략 테스트"""

import datetime

from src.strategy.data.models import HalfDayCandle, Period, Recent20DaysHalfDayCandles
from src.strategy.strategies.volatility_breakout import check_buy_signal


class TestVolatilityBreakoutSignal:
    """변동성 돌파 매수 시그널 테스트"""

    def test_signal_true_when_price_above_threshold(self):
        """현재가가 임계값보다 높을 때 True 반환"""
        # 20일치 데이터 생성, 모든 오전 노이즈 = 0.5
        candles = []
        base_date = datetime.date(2025, 10, 1)

        for i in range(20):
            date = base_date + datetime.timedelta(days=i)

            # 오전: range=1000, noise=0.5
            morning = HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,
                volume=1000.0
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=51500.0,
                low=50000.0,
                close=51000.0,
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        # Recent20DaysHalfDayCandles로 래핑
        history = Recent20DaysHalfDayCandles(candles)

        # 전일 오전 range = 1000
        # k값 (20일 평균 노이즈) = 0.5
        # 전일 오후 종가 = 51000 (= 당일 시가)
        # 임계값 = 51000 + (1000 * 0.5) = 51500

        current_price = 51600.0  # 임계값(51500)보다 높음

        result = check_buy_signal(history, current_price)

        assert result is True

    def test_signal_false_when_price_below_threshold(self):
        """현재가가 임계값보다 낮을 때 False 반환"""
        candles = []
        base_date = datetime.date(2025, 10, 1)

        for i in range(20):
            date = base_date + datetime.timedelta(days=i)

            morning = HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,
                volume=1000.0
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=51500.0,
                low=50000.0,
                close=51000.0,
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        # 임계값 = 51000 + (1000 * 0.5) = 51500
        current_price = 51400.0  # 임계값보다 낮음

        result = check_buy_signal(history, current_price)

        assert result is False

    def test_signal_false_when_price_equals_threshold(self):
        """현재가가 임계값과 같을 때 False 반환"""
        candles = []
        base_date = datetime.date(2025, 10, 1)

        for i in range(20):
            date = base_date + datetime.timedelta(days=i)

            morning = HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,
                volume=1000.0
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=51500.0,
                low=50000.0,
                close=51000.0,
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        # 임계값 = 51000 + (1000 * 0.5) = 51500
        current_price = 51500.0  # 임계값과 정확히 같음

        result = check_buy_signal(history, current_price)

        assert result is False

    def test_signal_with_different_noise_values(self):
        """다양한 노이즈 값으로 임계값 계산 확인"""
        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 노이즈가 0.05, 0.1, 0.15, ..., 1.0인 20일치 데이터
        for i in range(1, 21):
            date = base_date + datetime.timedelta(days=i)
            noise = i * 0.05

            range_value = 1000.0
            body_size = range_value * (1 - noise)

            morning = HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=50000.0 + range_value,
                low=50000.0,
                close=50000.0 + body_size,
                volume=1000.0
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        # k값 = (0.05 + 0.1 + ... + 1.0) / 20 = 0.525
        # 전일 오전 range = 1000
        # 전일 오후 종가 = 50500 (= 당일 시가)
        # 임계값 = 50500 + (1000 * 0.525) = 51025

        current_price = 51100.0  # 임계값보다 높음

        result = check_buy_signal(history, current_price)

        assert result is True

    def test_signal_uses_yesterday_morning_range(self):
        """전일 오전 레인지를 사용하는지 확인"""
        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 19일은 range=1000, 마지막 1일(전일)은 range=2000
        for i in range(19):
            date = base_date + datetime.timedelta(days=i)

            morning = HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,  # range=1000
                low=50000.0,
                close=50500.0,
                volume=1000.0
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=51500.0,
                low=50000.0,
                close=51000.0,
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        # 전일 (20일째)
        yesterday = base_date + datetime.timedelta(days=19)
        yesterday_morning = HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=52000.0,  # range=2000
            low=50000.0,
            close=51000.0,
            volume=1000.0
        )

        yesterday_afternoon = HalfDayCandle(
            date=yesterday,
            period=Period.AFTERNOON,
            open=51000.0,
            high=52000.0,
            low=50500.0,
            close=51500.0,
            volume=1500.0
        )

        candles.extend([yesterday_morning, yesterday_afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        # k값 = 0.5 (대부분 noise=0.5)
        # 전일 오전 range = 2000
        # 전일 오후 종가 = 51500 (= 당일 시가)
        # 임계값 = 51500 + (2000 * 0.5) = 52500

        current_price = 52600.0  # 임계값보다 높음

        result = check_buy_signal(history, current_price)

        assert result is True
