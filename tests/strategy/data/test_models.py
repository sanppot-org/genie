"""HalfDayCandle 모델 테스트"""

import datetime

import pytest
from pydantic import ValidationError

from src.strategy.data.models import HalfDayCandle, Period


class TestHalfDayCandle:
    """HalfDayCandle 모델 테스트"""

    def test_create_with_valid_data(self):
        """유효한 데이터로 모델 생성"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        assert candle.date == datetime.date(2025, 10, 13)
        assert candle.period == Period.MORNING
        assert candle.open == 50000.0
        assert candle.high == 51000.0
        assert candle.low == 49000.0
        assert candle.close == 50500.0
        assert candle.volume == 1234.56

    def test_create_with_afternoon_period(self):
        """오후 기간으로 모델 생성"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.AFTERNOON,
            open=50500.0,
            high=52000.0,
            low=50000.0,
            close=51500.0,
            volume=2345.67
        )

        assert candle.period == Period.AFTERNOON

    def test_range_property(self):
        """range 프로퍼티 계산 테스트"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        assert candle.range == 2000.0  # 51000 - 49000

    def test_volatility_property(self):
        """volatility 프로퍼티 계산 테스트"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        # (51000 - 49000) / 50000 = 0.04
        assert candle.volatility == pytest.approx(0.04, rel=1e-9)

    def test_volatility_with_zero_open(self):
        """시가가 0일 때 volatility 계산"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=0.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        # 0으로 나누면 inf
        assert candle.volatility == float('inf')

    def test_noise_property(self):
        """noise 프로퍼티 계산 테스트"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        # 1 - |50000 - 50500| / (51000 - 49000) = 1 - 500/2000 = 1 - 0.25 = 0.75
        assert candle.noise == pytest.approx(0.75, rel=1e-9)

    def test_noise_with_zero_range(self):
        """레인지가 0일 때 noise 계산"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=50000.0,  # 고가 = 저가
            low=50000.0,
            close=50000.0,
            volume=1234.56
        )

        # 레인지가 0이면 0 반환
        assert candle.noise == 0.0

    def test_return_rate_property(self):
        """return_rate 프로퍼티 계산 테스트"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        # (50500 - 50000) / 50000 = 500 / 50000 = 0.01
        assert candle.return_rate == pytest.approx(0.01, rel=1e-9)

    def test_return_rate_with_negative(self):
        """음수 수익률 계산"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=48000.0,
            close=49000.0,
            volume=1234.56
        )

        # (49000 - 50000) / 50000 = -1000 / 50000 = -0.02
        assert candle.return_rate == pytest.approx(-0.02, rel=1e-9)

    def test_return_rate_with_zero_open(self):
        """시가가 0일 때 return_rate 계산"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=0.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        # 0으로 나누면 inf
        assert candle.return_rate == float('inf')

    def test_from_dict(self):
        """from_dict 메서드 테스트"""
        data = {
            "date": "2025-10-13",
            "period": "morning",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "volume": 1234.56
        }

        candle = HalfDayCandle.from_dict(data)

        assert candle.date == datetime.date(2025, 10, 13)
        assert candle.period == Period.MORNING
        assert candle.open == 50000.0

    def test_to_dict(self):
        """to_dict 메서드 테스트"""
        candle = HalfDayCandle(
            date=datetime.date(2025, 10, 13),
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1234.56
        )

        result = candle.to_dict()

        assert result == {
            "date": "2025-10-13",
            "period": "morning",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "volume": 1234.56
        }

    def test_invalid_period(self):
        """잘못된 period 값"""
        with pytest.raises(ValidationError):
            HalfDayCandle(
                date=datetime.date(2025, 10, 13),
                period="evening",  # 잘못된 값
                open=50000.0,
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1234.56
            )

    def test_missing_required_field(self):
        """필수 필드 누락"""
        with pytest.raises(ValidationError):
            HalfDayCandle(
                date=datetime.date(2025, 10, 13),
                period=Period.MORNING,
                # open 필드 누락
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1234.56
            )

    def test_invalid_type(self):
        """잘못된 타입"""
        with pytest.raises(ValidationError):
            HalfDayCandle(
                date=datetime.date(2025, 10, 13),
                period=Period.MORNING,
                open="invalid",  # 문자열은 불가
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1234.56
            )


class TestRecent20DaysHalfDayCandles:
    """Recent20DaysHalfDayCandles 래퍼 클래스 테스트"""

    def test_create_with_candles(self):
        """캔들 리스트로 생성"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        for i in range(20):
            date = datetime.date(2025, 10, 1) + datetime.timedelta(days=i)
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

        history = Recent20DaysHalfDayCandles(candles)

        assert len(history.candles) == 40

    def test_morning_candles_property(self):
        """오전 캔들만 필터링"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        for i in range(20):
            date = datetime.date(2025, 10, 1) + datetime.timedelta(days=i)
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

        history = Recent20DaysHalfDayCandles(candles)
        morning = history.morning_candles

        assert len(morning) == 20
        assert all(c.period == Period.MORNING for c in morning)

    def test_afternoon_candles_property(self):
        """오후 캔들만 필터링"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        for i in range(20):
            date = datetime.date(2025, 10, 1) + datetime.timedelta(days=i)
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

        history = Recent20DaysHalfDayCandles(candles)
        afternoon = history.afternoon_candles

        assert len(afternoon) == 20
        assert all(c.period == Period.AFTERNOON for c in afternoon)

    def test_yesterday_morning_property(self):
        """전일 오전 캔들 조회"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        for i in range(20):
            date = datetime.date(2025, 10, 1) + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0 + i * 1000,
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

        history = Recent20DaysHalfDayCandles(candles)
        yesterday_morning = history.yesterday_morning

        # 마지막 오전 캔들 (20일째)
        assert yesterday_morning.open == 69000.0
        assert yesterday_morning.period == Period.MORNING

    def test_yesterday_afternoon_property(self):
        """전일 오후 캔들 조회"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        for i in range(20):
            date = datetime.date(2025, 10, 1) + datetime.timedelta(days=i)
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
                open=50500.0 + i * 1000,
                high=52000.0,
                low=50000.0,
                close=51500.0,
                volume=1500.0
            ))

        history = Recent20DaysHalfDayCandles(candles)
        yesterday_afternoon = history.yesterday_afternoon

        # 마지막 오후 캔들 (20일째)
        assert yesterday_afternoon.open == 69500.0
        assert yesterday_afternoon.period == Period.AFTERNOON

    def test_calculate_morning_noise_average(self):
        """오전 노이즈 평균 계산"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        for i in range(20):
            date = datetime.date(2025, 10, 1) + datetime.timedelta(days=i)
            # 오전: noise = 0.5
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50500.0,  # |50000-50500|/1000 = 0.5, noise = 0.5
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
        avg = history.calculate_morning_noise_average()

        assert avg == pytest.approx(0.5, rel=1e-9)

    def test_calculate_threshold(self):
        """변동성 돌파 임계값 계산"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles
        from src.strategy.strategies.volatility_breakout import _calculate_threshold

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 20일치 데이터 생성 (모든 오전 노이즈 = 0.5)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,  # range=1000
                low=50000.0,
                close=50500.0,  # noise=0.5
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51000.0,  # 이것이 다음날 오전 시가가 됨
                volume=1500.0
            ))

        history = Recent20DaysHalfDayCandles(candles)

        # 전일 오전 range = 1000
        # k값 (20일 평균 노이즈) = 0.5
        # 전일 오후 종가 = 51000 (= 당일 시가)
        # 임계값 = 51000 + (1000 * 0.5) = 51500
        threshold = _calculate_threshold(history)

        assert threshold == pytest.approx(51500.0, rel=1e-9)

    def test_calculate_threshold_uses_yesterday_afternoon_close(self):
        """임계값 계산 시 전일 오후 종가를 당일 시가로 사용"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles
        from src.strategy.strategies.volatility_breakout import _calculate_threshold

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 19일은 동일한 데이터
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
                close=51000.0,
                volume=1500.0
            ))

        # 20일째 (전일): 오후 종가를 다르게 설정
        yesterday = base_date + datetime.timedelta(days=19)
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,  # range=1000
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
            close=60000.0,  # 특별히 높은 종가 (당일 시가가 됨)
            volume=1500.0
        ))

        history = Recent20DaysHalfDayCandles(candles)

        # k = 0.5, 전일 오전 range = 1000
        # 당일 시가 = 전일 오후 종가 = 60000
        # 임계값 = 60000 + (1000 * 0.5) = 60500
        threshold = _calculate_threshold(history)

        assert threshold == pytest.approx(60500.0, rel=1e-9)

    def test_calculate_threshold_with_different_k(self):
        """다양한 k값으로 임계값 계산"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles
        from src.strategy.strategies.volatility_breakout import _calculate_threshold

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 노이즈가 0.05, 0.1, 0.15, ..., 1.0인 20일치
        for i in range(1, 21):
            date = base_date + datetime.timedelta(days=i)
            noise = i * 0.05
            range_value = 1000.0
            body_size = range_value * (1 - noise)

            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=50000.0 + range_value,
                low=50000.0,
                close=50000.0 + body_size,
                volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=52000.0,  # 당일 시가
                volume=1500.0
            ))

        history = Recent20DaysHalfDayCandles(candles)

        # k값 = (0.05 + 0.1 + ... + 1.0) / 20 = 0.525
        # 전일 오전 range = 1000
        # 당일 시가 = 52000
        # 임계값 = 52000 + (1000 * 0.525) = 52525
        threshold = _calculate_threshold(history)

        assert threshold == pytest.approx(52525.0, rel=1e-9)

    def test_calculate_ma_score_all_above(self):
        """모든 이평선이 전일 오전 종가보다 클 때 1.0 반환"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 20일치 데이터: 오전 종가가 점진적으로 상승 (50000 → 69000)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            morning_close = 50000.0 + i * 1000  # 50000, 51000, ..., 69000
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

        # 전일(19일째) 오전 종가 = 69000
        # 3일 이평선 = (67000 + 68000 + 69000) / 3 = 68000
        # 5일 이평선 = (65000 + 66000 + 67000 + 68000 + 69000) / 5 = 67000
        # 10일 이평선 = (60000 + ... + 69000) / 10 = 64500
        # 20일 이평선 = (50000 + ... + 69000) / 20 = 59500
        # 모든 이평선이 전일 오전 종가(69000)보다 작으므로 0.0
        #
        # 수정: 상승 추세에서는 이평선이 현재가보다 작습니다.
        # 다시 설계: 이평선이 전일 오전 종가보다 크려면 하락 후 반등 패턴이 필요

        ma_score = history.calculate_ma_score()

        # 상승 추세: 모든 이평선 < 전일 오전 종가 → 0.0
        assert ma_score == pytest.approx(0.0, rel=1e-9)

    def test_calculate_ma_score_all_below(self):
        """모든 이평선이 전일 오전 종가보다 작을 때 0.0 반환"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 20일치 데이터: 오전 종가가 모두 동일 (50000)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50000.0,  # 모두 동일
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

        # 전일 오전 종가 = 50000
        # 모든 이평선 = 50000 (전일 오전 종가와 동일하므로 > 조건 불만족)
        ma_score = history.calculate_ma_score()

        assert ma_score == pytest.approx(0.0, rel=1e-9)

    def test_calculate_ma_score_partial_above(self):
        """일부 이평선만 전일 오전 종가보다 클 때 적절한 비율 반환"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 시나리오: 하락 후 반등
        # 1~17일: 60000
        # 18~19일: 50000 (하락)
        # 20일(전일): 55000 (반등)
        for i in range(17):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=60000.0,  # 고점
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

        # 18~19일: 하락
        for i in range(17, 19):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=50000.0,  # 하락
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

        # 20일(전일): 반등
        yesterday = base_date + datetime.timedelta(days=19)
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=50000.0,
            close=55000.0,  # 반등
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

        # 전일 오전 종가 = 55000
        # 3일 이평선 = (50000 + 50000 + 55000) / 3 = 51666.67 < 55000
        # 5일 이평선 = (50000 + 50000 + 50000 + 50000 + 55000) / 5 = 51000 < 55000
        # 10일 이평선 = (60000*8 + 50000*2) / 10 = 58000 > 55000 ✓
        # 20일 이평선 = (60000*17 + 50000*2 + 55000) / 20 = 59250 > 55000 ✓
        # 2개 만족 → 2/4 = 0.5
        ma_score = history.calculate_ma_score()

        assert ma_score == pytest.approx(0.5, rel=1e-9)

    def test_calculate_ma_score_all_above_scenario(self):
        """모든 이평선이 전일 오전 종가보다 큰 시나리오"""
        from src.strategy.data.models import Recent20DaysHalfDayCandles

        candles = []
        base_date = datetime.date(2025, 10, 1)

        # 시나리오: 장기 상승 후 급락
        # 1~19일: 70000 (고점 유지)
        # 20일(전일): 50000 (급락)
        for i in range(19):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date,
                period=Period.MORNING,
                open=50000.0,
                high=51000.0,
                low=50000.0,
                close=70000.0,  # 고점
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

        # 20일(전일): 급락
        yesterday = base_date + datetime.timedelta(days=19)
        candles.append(HalfDayCandle(
            date=yesterday,
            period=Period.MORNING,
            open=50000.0,
            high=51000.0,
            low=50000.0,
            close=50000.0,  # 급락
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

        # 전일 오전 종가 = 50000
        # 3일 이평선 = (70000 + 70000 + 50000) / 3 = 63333.33 > 50000 ✓
        # 5일 이평선 = (70000*4 + 50000) / 5 = 66000 > 50000 ✓
        # 10일 이평선 = (70000*9 + 50000) / 10 = 68000 > 50000 ✓
        # 20일 이평선 = (70000*19 + 50000) / 20 = 69000 > 50000 ✓
        # 4개 모두 만족 → 4/4 = 1.0
        ma_score = history.calculate_ma_score()

        assert ma_score == pytest.approx(1.0, rel=1e-9)
