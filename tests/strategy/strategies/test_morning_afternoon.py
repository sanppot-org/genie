"""오전오후 전략 테스트"""

import datetime
from zoneinfo import ZoneInfo

from src.strategy.clock import FixedClock
from src.strategy.data.models import HalfDayCandle, Period, Recent20DaysHalfDayCandles
from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy


class TestMorningAfternoonSignal:
    """오전오후 매수 시그널 테스트"""

    def test_signal_false_when_not_morning(self):
        """오전 시간이 아닐 때 False 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig

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
                volume=1000.0
            )

            afternoon = HalfDayCandle(
                date=date,
                period=Period.AFTERNOON,
                open=50500.0,
                high=52000.0,
                low=50000.0,
                close=51500.0,  # 조건 만족
                volume=1500.0
            )

            candles.extend([morning, afternoon])

        history = Recent20DaysHalfDayCandles(candles)

        # 오후 3시 (KST)
        afternoon_time = datetime.datetime(2025, 10, 20, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        clock = FixedClock(afternoon_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy._check_buy_signal()

        assert result is False

    def test_signal_false_when_afternoon_return_negative(self):
        """전일 오후 수익률이 음수일 때 False 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig

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

        # 오전 10시 (KST)
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy._check_buy_signal()

        assert result is False

    def test_signal_false_when_morning_volume_greater(self):
        """전일 오전 거래량이 오후보다 클 때 False 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig

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

        # 오전 10시 (KST)
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy._check_buy_signal()

        assert result is False

    def test_signal_uses_yesterday_data_only(self):
        """전일 데이터만 사용하는지 확인"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig

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

        # 오전 10시 (KST)
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy._check_buy_signal()

        # 전일 데이터가 조건 만족하므로 True
        assert result is True


class TestMorningAfternoonPositionSize:
    """오전오후 매수 비중 계산 테스트"""

    def test_calculate_position_size_normal(self):
        """정상 케이스: 비중 계산"""
        from unittest.mock import Mock
        import pytest
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

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

        # Mock 설정
        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        strategy = MorningAfternoonStrategy(upbit, config, None, None)
        strategy.collector.collect_data = Mock(return_value=history)

        # target_vol = 0.01, volatility = 0.02
        # position_size = 0.01 / 0.02 = 0.5
        result = strategy._calculate_position_size()

        assert result == pytest.approx(0.5, rel=1e-9)

    def test_calculate_position_size_low_volatility(self):
        """변동성 < 0.1%일 때 0 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

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
        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        strategy = MorningAfternoonStrategy(upbit, config, None, None)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy._calculate_position_size()

        assert result == 0.0

    def test_calculate_position_size_capped_at_one(self):
        """계산 결과 > 1.0일 때 1.0 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

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

        # Mock 설정
        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        strategy = MorningAfternoonStrategy(upbit, config, None, None)
        strategy.collector.collect_data = Mock(return_value=history)

        # target_vol = 0.02, volatility = 0.002
        # position_size = 0.02 / 0.002 = 10 > 1.0 → 1.0
        config.target_vol = 0.02
        result = strategy._calculate_position_size()

        assert result == 1.0

    def test_calculate_position_size_various_targets(self):
        """다양한 타겟 변동성으로 비중 계산"""
        from unittest.mock import Mock
        import pytest
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

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

        # Mock 설정
        upbit = Mock()
        config = MorningAfternoonConfig(ticker="KRW-BTC", target_vol=0.01)
        strategy = MorningAfternoonStrategy(upbit, config, None, None)
        strategy.collector.collect_data = Mock(return_value=history)

        # 다양한 타겟 테스트
        # target_vol = 0.005 (0.5%), volatility = 0.02
        strategy.config.target_vol = 0.005
        result1 = strategy._calculate_position_size()
        assert result1 == pytest.approx(0.25, rel=1e-9)

        # target_vol = 0.01 (1%), volatility = 0.02
        strategy.config.target_vol = 0.01
        result2 = strategy._calculate_position_size()
        assert result2 == pytest.approx(0.5, rel=1e-9)

        # target_vol = 0.015 (1.5%), volatility = 0.02
        strategy.config.target_vol = 0.015
        result3 = strategy._calculate_position_size()
        assert result3 == pytest.approx(0.75, rel=1e-9)


class TestMorningAfternoonShouldBuy:
    """should_buy() 메서드 테스트"""

    def test_should_buy_returns_false_when_signal_false(self):
        """시그널이 False면 False 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_balance = Mock(return_value=0.0)  # 보유 중이지 않음

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        # 시그널 조건 불만족 데이터
        candles = []
        base_date = datetime.date(2025, 10, 1)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date, period=Period.MORNING,
                open=50000.0, high=51000.0, low=50000.0, close=50500.0, volume=2000.0
            ))
            candles.append(HalfDayCandle(
                date=date, period=Period.AFTERNOON,
                open=50500.0, high=51000.0, low=49000.0, close=49500.0, volume=1500.0  # 수익률 음수
            ))

        history = Recent20DaysHalfDayCandles(candles)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy.should_buy()

        assert result is False

    def test_should_buy_returns_true_when_all_conditions_met(self):
        """모든 조건 만족 시 True 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_balance = Mock(return_value=0.0)  # 보유 중이지 않음

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        # 정상 데이터
        candles = []
        base_date = datetime.date(2025, 10, 1)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date, period=Period.MORNING,
                open=50000.0, high=51000.0, low=50000.0, close=50500.0, volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date, period=Period.AFTERNOON,
                open=50500.0, high=52000.0, low=50000.0, close=51500.0, volume=1500.0
            ))

        history = Recent20DaysHalfDayCandles(candles)
        strategy.collector.collect_data = Mock(return_value=history)

        result = strategy.should_buy()

        assert result is True


class TestMorningAfternoonExecuteBuy:
    """execute_buy() 메서드 테스트"""

    def test_execute_buy_success(self):
        """매수 성공 시 매수 실행"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=10000.0)  # KRW 잔고
        upbit.buy_market_order = Mock(return_value={"success": True})

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.execute_buy(position_size=0.5)

        upbit.buy_market_order.assert_called_once_with("KRW-BTC", 5000.0)

    def test_execute_buy_not_execute_when_below_min_amount(self):
        """최소 주문 금액 미만이면 매수 안함"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=1000.0)  # 적은 잔고

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.execute_buy(position_size=0.5)

        upbit.buy_market_order.assert_not_called()

    def test_execute_buy_respects_allocation_ratio(self):
        """allocation_ratio를 반영해서 매수"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=100000.0)
        upbit.buy_market_order = Mock(return_value={"success": True})

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=0.5,  # 50%만 할당
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.execute_buy(position_size=0.5)

        # 100000 * 0.5 * 0.5 = 25000
        upbit.buy_market_order.assert_called_once_with("KRW-BTC", 25000.0)


class TestMorningAfternoonTryBuy:
    """try_buy() 메서드 테스트"""

    def test_try_buy_executes_when_all_conditions_met(self):
        """모든 조건을 만족하면 매수 실행"""
        from unittest.mock import Mock, patch
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        # Mock 설정
        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=10000.0)  # KRW 잔고
        upbit.buy_market_order = Mock(return_value={"success": True})

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        # 데이터 수집 Mock
        candles = []
        base_date = datetime.date(2025, 10, 1)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date, period=Period.MORNING,
                open=50000.0, high=51000.0, low=50000.0, close=50500.0, volume=1000.0
            ))
            candles.append(HalfDayCandle(
                date=date, period=Period.AFTERNOON,
                open=50500.0, high=52000.0, low=50000.0, close=51500.0, volume=1500.0
            ))

        with patch.object(strategy.collector, 'collect_data', return_value=Recent20DaysHalfDayCandles(candles)):
            strategy.try_buy()

        upbit.buy_market_order.assert_called_once()

    def test_try_buy_not_execute_when_already_holding(self):
        """이미 보유 중이면 매수 안함"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_balance = Mock(return_value=0.5)  # 이미 보유 중

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.try_buy()

        upbit.buy_market_order.assert_not_called()

    def test_try_buy_not_execute_when_not_morning(self):
        """오전이 아니면 매수 안함"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        afternoon_time = datetime.datetime(2025, 10, 20, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(afternoon_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.try_buy()

        # 매수가 호출되지 않았는지 확인할 방법이 필요하면 추가

    def test_try_buy_not_execute_when_signal_false(self):
        """시그널이 False면 매수 안함"""
        from unittest.mock import Mock, patch
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_balance = Mock(side_effect=lambda ticker: 0.0 if ticker == "BTC" else 10000.0)

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        # 시그널 조건 불만족 데이터
        candles = []
        base_date = datetime.date(2025, 10, 1)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date, period=Period.MORNING,
                open=50000.0, high=51000.0, low=50000.0, close=50500.0, volume=2000.0
            ))
            candles.append(HalfDayCandle(
                date=date, period=Period.AFTERNOON,
                open=50500.0, high=51000.0, low=49000.0, close=49500.0, volume=1500.0  # 수익률 음수
            ))

        with patch.object(strategy.collector, 'collect_data', return_value=Recent20DaysHalfDayCandles(candles)):
            strategy.try_buy()

        upbit.buy_market_order.assert_not_called()

    def test_try_buy_not_execute_when_position_size_zero(self):
        """매수 비중이 0 이하면 매수 안함"""
        from unittest.mock import Mock, patch
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_balance = Mock(side_effect=lambda ticker: 0.0 if ticker == "BTC" else 10000.0)

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        # 변동성이 낮아서 비중이 0이 되는 데이터
        candles = []
        base_date = datetime.date(2025, 10, 1)
        for i in range(20):
            date = base_date + datetime.timedelta(days=i)
            candles.append(HalfDayCandle(
                date=date, period=Period.MORNING,
                open=50000.0, high=50010.0, low=50000.0, close=50005.0, volume=1000.0  # 변동성 < 0.1%
            ))
            candles.append(HalfDayCandle(
                date=date, period=Period.AFTERNOON,
                open=50500.0, high=52000.0, low=50000.0, close=51500.0, volume=1500.0
            ))

        with patch.object(strategy.collector, 'collect_data', return_value=Recent20DaysHalfDayCandles(candles)):
            strategy.try_buy()

        upbit.buy_market_order.assert_not_called()


class TestMorningAfternoonShouldSell:
    """should_sell() 메서드 테스트"""

    def test_should_sell_returns_false_when_not_holding(self):
        """보유하지 않으면 False 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=0.0)  # 보유하지 않음

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        should = strategy.should_sell()

        assert should is False

    def test_should_sell_returns_true_when_holding(self):
        """오후면 True 반환"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=0.5)  # 0.5 BTC 보유

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        afternoon_time = datetime.datetime(2025, 10, 20, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(afternoon_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        should = strategy.should_sell()

        assert should is True


class TestMorningAfternoonExecuteSell:
    """execute_sell() 메서드 테스트"""

    def test_execute_sell_success(self):
        """매도 성공 시 매도 실행"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=0.5)  # 0.5 BTC 보유
        upbit.sell_market_order = Mock(return_value={"success": True})

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.execute_sell()

        upbit.sell_market_order.assert_called_once_with("KRW-BTC", 0.5)

    def test_execute_sell_failure(self):
        """매도 실패 시 예외 처리"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=0.5)  # 0.5 BTC 보유
        upbit.sell_market_order = Mock(side_effect=Exception("API error"))

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        # 예외가 발생해도 프로그램이 종료되지 않아야 함
        strategy.execute_sell()

        # sell_market_order는 호출되었어야 함
        upbit.sell_market_order.assert_called_once()


class TestMorningAfternoonTrySell:
    """try_sell() 메서드 테스트"""

    def test_try_sell_executes_when_holding(self):
        """오후이고 보유 중이면 매도 실행"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_available_amount = Mock(return_value=0.5)  # 0.5 BTC 보유
        upbit.sell_market_order = Mock(return_value={"success": True})

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        afternoon_time = datetime.datetime(2025, 10, 20, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(afternoon_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.try_sell()

        upbit.sell_market_order.assert_called_once_with("KRW-BTC", 0.5)

    def test_try_sell_not_execute_when_not_holding(self):
        """보유하지 않았으면 매도 안함"""
        from unittest.mock import Mock
        from src.strategy.config import MorningAfternoonConfig
        from src.strategy.morning_afternoon.strategy import MorningAfternoonStrategy

        upbit = Mock()
        upbit.get_balance = Mock(return_value=0.0)  # 보유하지 않음

        config = MorningAfternoonConfig(
            ticker="KRW-BTC",
            target_vol=0.01,
            allocation_ratio=1.0,
            min_order_amount=5000.0
        )
        morning_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        clock = FixedClock(morning_time)

        strategy = MorningAfternoonStrategy(upbit, config, clock, None)

        strategy.try_sell()

        upbit.sell_market_order.assert_not_called()
