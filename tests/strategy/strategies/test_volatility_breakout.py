"""변동성 돌파 전략 테스트"""

import datetime
from unittest.mock import Mock

import pytest

from src.strategy.config import VolatilityBreakoutConfig
from src.strategy.data.models import HalfDayCandle, Period, Recent20DaysHalfDayCandles
from src.strategy.volatility_breakout.strategy import VolatilityBreakoutStrategy
from src.upbit.upbit_api import UpbitAPI


class TestVolatilityBreakoutPositionSize:
    """변동성 돌파 매수 비중 계산 테스트"""

    def test_calculate_position_size_normal(self):
        """정상 케이스: 비중 계산"""

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

        # Mock 설정
        mock_upbit = Mock(spec=UpbitAPI)
        config = VolatilityBreakoutConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000
        )

        strategy = VolatilityBreakoutStrategy(upbit=mock_upbit, config=config, clock=None, scheduler=None)
        strategy.collector.collect_data = Mock(return_value=history)

        # target_vol = 0.01, yesterday_morning.volatility = 0.02, ma_score = 1.0
        # position_size = (0.01 / 0.02) * 1.0 = 0.5
        result = strategy._calculate_position_size()

        assert result == pytest.approx(0.5, rel=1e-9)

    def test_calculate_position_size_low_volatility(self):
        """변동성 < 0.1%일 때 0 반환"""

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

        # Mock 설정
        mock_upbit = Mock(spec=UpbitAPI)
        config = VolatilityBreakoutConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000
        )

        strategy = VolatilityBreakoutStrategy(upbit=mock_upbit, config=config, clock=None, scheduler=None)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy._calculate_position_size()

        assert result == 0.0

    def test_calculate_position_size_capped_at_one(self):
        """계산 결과 > 1.0일 때 1.0 반환"""

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

        # Mock 설정
        mock_upbit = Mock(spec=UpbitAPI)
        config = VolatilityBreakoutConfig(
            ticker="KRW-BTC",
            target_vol=0.02,
            allocation_ratio=1.0,
            min_order_amount=5000
        )

        strategy = VolatilityBreakoutStrategy(upbit=mock_upbit, config=config, clock=None, scheduler=None)
        strategy.collector.collect_data = Mock(return_value=history)

        # target_vol = 0.02, volatility = 0.002, ma_score = 1.0
        # position_size = (0.02 / 0.002) * 1.0 = 10 > 1.0 → 1.0
        result = strategy._calculate_position_size()

        assert result == 1.0

    def test_calculate_position_size_zero_when_ma_score_zero(self):
        """ma_score가 0일 때 0 반환"""

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

        # Mock 설정
        mock_upbit = Mock(spec=UpbitAPI)
        config = VolatilityBreakoutConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000
        )

        strategy = VolatilityBreakoutStrategy(upbit=mock_upbit, config=config, clock=None, scheduler=None)
        strategy.collector.collect_data = Mock(return_value=history)

        # ma_score = 0 → position_size = (0.01 / volatility) * 0 = 0
        result = strategy._calculate_position_size()

        assert result == 0.0

    def test_calculate_position_size_with_partial_ma_score(self):
        """일부 이평선만 만족할 때 비중 계산"""

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

        # Mock 설정
        mock_upbit = Mock(spec=UpbitAPI)
        config = VolatilityBreakoutConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000
        )

        strategy = VolatilityBreakoutStrategy(upbit=mock_upbit, config=config, clock=None, scheduler=None)
        strategy.collector.collect_data = Mock(return_value=history)

        # target_vol = 0.01, volatility = 0.02, ma_score = 0.5
        # position_size = (0.01 / 0.02) * 0.5 = 0.25
        result = strategy._calculate_position_size()

        assert result == pytest.approx(0.25, rel=1e-9)
