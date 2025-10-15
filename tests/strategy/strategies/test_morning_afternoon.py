"""오전오후 전략 테스트"""

import datetime

from src.strategy.data.models import HalfDayCandle, Period, Recent20DaysHalfDayCandles
from src.strategy.strategies.morning_afternoon import check_buy_signal


class TestMorningAfternoonSignal:
    """오전오후 매수 시그널 테스트"""

    def test_signal_true_when_all_conditions_met(self):
        """모든 조건을 만족할 때 True 반환"""
        # 20일치 데이터 생성
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
                volume=1000.0  # 오전 거래량
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,  # 오후 수익률 = (51500-50500)/50500 > 0
                volume=1500.0  # 오후 거래량 > 오전 거래량
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        result = check_buy_signal(history)

        assert result is True

    def test_signal_false_when_afternoon_return_negative(self):
        """전일 오후 수익률이 음수일 때 False 반환"""
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
                high=51000.0,
                low=49000.0,
                close=49500.0,  # 오후 수익률 = (49500-50500)/50500 < 0
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        result = check_buy_signal(history)

        assert result is False

    def test_signal_false_when_afternoon_return_zero(self):
        """전일 오후 수익률이 0일 때 False 반환"""
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
                high=51000.0,
                low=50000.0,
                close=50500.0,  # 오후 수익률 = 0
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        result = check_buy_signal(history)

        assert result is False

    def test_signal_false_when_morning_volume_greater(self):
        """전일 오전 거래량이 오후보다 클 때 False 반환"""
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
                volume=2000.0  # 오전 거래량이 더 큼
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,  # 수익률은 양수
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        result = check_buy_signal(history)

        assert result is False

    def test_signal_false_when_volumes_equal(self):
        """전일 오전/오후 거래량이 같을 때 False 반환"""
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
                volume=1500.0  # 같은 거래량
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0  # 같은 거래량
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        result = check_buy_signal(history)

        assert result is False

    def test_signal_uses_yesterday_data_only(self):
        """전일 데이터만 사용하는지 확인"""
        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 19일은 조건 불만족
        for i in range(19):
            date = base_date + datetime.timedelta(days=i)

            morning = HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,
                volume=2000.0  # 오전이 더 큼
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=51000.0,
                low=49000.0,
                close=49500.0,  # 수익률 음수
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        # 전일 (20일째)만 조건 만족
        yesterday = base_date + datetime.timedelta(days=19)
        yesterday_morning = HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=50000.0,
            close=50500.0,
            volume=1000.0  # 오전 거래량
        )

        yesterday_afternoon = HalfDayCandle(
            date=yesterday,
            period=Period.AFTERNOON,
            open=50500.0,
            high=52000.0,
            low=50000.0,
            close=51500.0,  # 수익률 양수
            volume=1500.0  # 오후 거래량 > 오전
        )

        candles.extend([yesterday_morning, yesterday_afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        result = check_buy_signal(history)

        # 전일 데이터가 조건 만족하므로 True
        assert result is True

    def test_signal_with_small_positive_return(self):
        """작은 양수 수익률로도 시그널 발생"""
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
                high=51000.0,
                low=50000.0,
                close=50501.0,  # 아주 작은 양수 수익률
                volume=1001.0  # 아주 작은 차이로 오후가 더 큼
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        result = check_buy_signal(history)

        assert result is True


class TestMorningAfternoonPositionSize:
    """오전오후 매수 비중 계산 테스트"""

    def test_calculate_position_size_normal(self):
        """정상 케이스: 비중 계산"""
        from src.strategy.strategies.morning_afternoon import calculate_position_size
        import pytest

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 19일
        for i in range(19):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,
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

        # 전일 (변동성 = 0.02)
        yesterday = base_date + datetime.timedelta(days=19)
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,  # range=1000, volatility=1000/50000=0.02
            low=50000.0,
            close=50500.0,
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

        # target_vol = 0.01, volatility = 0.02
        # position_size = 0.01 / 0.02 = 0.5
        target_vol = 0.01
        result = calculate_position_size(history, target_vol)

        assert result == pytest.approx(0.5, rel=1e-9)

    def test_calculate_position_size_low_volatility(self):
        """변동성 < 0.1%일 때 0 반환"""
        from src.strategy.strategies.morning_afternoon import calculate_position_size

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
        from src.strategy.strategies.morning_afternoon import calculate_position_size

        candles = []
        base_date = datetime.date(2025, 10, 1)

        for i in range(19):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,
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
            close=50050.0,
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

        # target_vol = 0.02, volatility = 0.002
        # position_size = 0.02 / 0.002 = 10 > 1.0 → 1.0
        target_vol = 0.02
        result = calculate_position_size(history, target_vol)

        assert result == 1.0

    def test_calculate_position_size_various_targets(self):
        """다양한 타겟 변동성으로 비중 계산"""
        from src.strategy.strategies.morning_afternoon import calculate_position_size
        import pytest

        candles = []
        base_date = datetime.date(2025, 10, 1)

        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,  # volatility = 0.02
                low=50000.0,
                close=50500.0,
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

        # 다양한 타겟 테스트
        # target_vol = 0.005 (0.5%), volatility = 0.02
        result1 = calculate_position_size(history, 0.005)
        assert result1 == pytest.approx(0.25, rel=1e-9)

        # target_vol = 0.01 (1%), volatility = 0.02
        result2 = calculate_position_size(history, 0.01)
        assert result2 == pytest.approx(0.5, rel=1e-9)

        # target_vol = 0.015 (1.5%), volatility = 0.02
        result3 = calculate_position_size(history, 0.015)
        assert result3 == pytest.approx(0.75, rel=1e-9)
