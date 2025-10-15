"""변동성 돌파 전략 테스트"""

import datetime
from zoneinfo import ZoneInfo

from src.strategy.data.models import HalfDayCandle, Period, Recent20DaysHalfDayCandles
from src.strategy.strategies.volatility_breakout import check_buy_signal


class TestVolatilityBreakoutSignal:
    """변동성 돌파 매수 시그널 테스트"""

    def test_signal_false_when_not_morning(self):
        """오전 시간이 아닐 때 False 반환"""
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

        # 가격은 임계값보다 높지만 오후 시간
        current_price = 51600.0
        afternoon_time = datetime.datetime(2025, 10, 20, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        result = check_buy_signal(history, current_price, now=afternoon_time)

        assert result is False

    def test_signal_true_when_morning_and_price_above_threshold(self):
        """오전이고 현재가가 임계값보다 높을 때 True 반환"""
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

        current_price = 51600.0
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        result = check_buy_signal(history, current_price, now=morning_time)

        assert result is True

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
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        result = check_buy_signal(history, current_price, now=morning_time)

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
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        result = check_buy_signal(history, current_price, now=morning_time)

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
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        result = check_buy_signal(history, current_price, now=morning_time)

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
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        result = check_buy_signal(history, current_price, now=morning_time)

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
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        result = check_buy_signal(history, current_price, now=morning_time)

        assert result is True


class TestVolatilityBreakoutPositionSize:
    """변동성 돌파 매수 비중 계산 테스트"""

    def test_calculate_position_size_normal(self):
        """정상 케이스: 비중 계산"""
        from src.strategy.strategies.volatility_breakout import calculate_position_size
        import pytest

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 시나리오: 장기 상승 후 급락 (ma_score = 1.0)
        for i in range(19):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=70000.0,
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0
            ))

        # 전일: 급락 (변동성 = 0.02)
        yesterday = base_date + datetime.timedelta(days=19)
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,  # range=1000
            low=50000.0,
            close=50000.0,  # volatility = 1000/50000 = 0.02
            volume=1000.0
        ))
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.AFTERNOON,
            open=50500.0,
            high=52000.0,
            low=50000.0,
            close=51500.0,
            volume=1500.0
        ))

        history = Recent20DaysHalfDayCandles(candles)

        # target_vol = 0.01, yesterday_morning.volatility = 0.02, ma_score = 1.0
        # position_size = (0.01 / 0.02) * 1.0 = 0.5
        target_vol = 0.01
        result = calculate_position_size(history, target_vol)

        assert result == pytest.approx(0.5, rel=1e-9)

    def test_calculate_position_size_low_volatility(self):
        """변동성 < 0.1%일 때 0 반환"""
        from src.strategy.strategies.volatility_breakout import calculate_position_size

        candles = []
        base_date = datetime.date(2025, 10, 1)

        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=50010.0,  # range=10, volatility=10/50000=0.0002 < 0.001
                low=50000.0,
                close=50005.0,
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0
            ))

        history = Recent20DaysHalfDayCandles(candles)

        target_vol = 0.01
        result = calculate_position_size(history, target_vol)

        assert result == 0.0

    def test_calculate_position_size_capped_at_one(self):
        """계산 결과 > 1.0일 때 1.0 반환"""
        from src.strategy.strategies.volatility_breakout import calculate_position_size

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # ma_score = 1.0 시나리오
        for i in range(19):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=70000.0,
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0
            ))

        # 전일: 낮은 변동성
        yesterday = base_date + datetime.timedelta(days=19)
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=50100.0,  # range=100, volatility=100/50000=0.002
            low=50000.0,
            close=50000.0,
            volume=1000.0
        ))
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.AFTERNOON,
            open=50500.0,
            high=52000.0,
            low=50000.0,
            close=51500.0,
            volume=1500.0
        ))

        history = Recent20DaysHalfDayCandles(candles)

        # target_vol = 0.02, volatility = 0.002, ma_score = 1.0
        # position_size = (0.02 / 0.002) * 1.0 = 10 > 1.0 → 1.0
        target_vol = 0.02
        result = calculate_position_size(history, target_vol)

        assert result == 1.0

    def test_calculate_position_size_zero_when_ma_score_zero(self):
        """ma_score가 0일 때 0 반환"""
        from src.strategy.strategies.volatility_breakout import calculate_position_size

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 상승 추세: ma_score = 0
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            morning_close = 50000.0 + i * 1000
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=morning_close,
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0
            ))

        history = Recent20DaysHalfDayCandles(candles)

        # ma_score = 0 → position_size = (0.01 / volatility) * 0 = 0
        target_vol = 0.01
        result = calculate_position_size(history, target_vol)

        assert result == 0.0

    def test_calculate_position_size_with_partial_ma_score(self):
        """일부 이평선만 만족할 때 비중 계산"""
        from src.strategy.strategies.volatility_breakout import calculate_position_size
        import pytest

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # ma_score = 0.5 시나리오
        for i in range(17):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=60000.0,
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0
            ))

        for i in range(17, 19):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50000.0,
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0
            ))

        yesterday = base_date + datetime.timedelta(days=19)
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,  # range=1000
            low=50000.0,
            close=55000.0,  # volatility = 1000/50000 = 0.02
            volume=1000.0
        ))
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.AFTERNOON,
            open=50500.0,
            high=52000.0,
            low=50000.0,
            close=51500.0,
            volume=1500.0
        ))

        history = Recent20DaysHalfDayCandles(candles)

        # target_vol = 0.01, volatility = 0.02, ma_score = 0.5
        # position_size = (0.01 / 0.02) * 0.5 = 0.25
        target_vol = 0.01
        result = calculate_position_size(history, target_vol)

        assert result == pytest.approx(0.25, rel=1e-9)
