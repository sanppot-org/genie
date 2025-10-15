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
