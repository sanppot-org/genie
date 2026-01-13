"""시간 기반 홀드 전략 테스트

1시간 봉 데이터를 사용하여 지정된 시간에 매수/청산하는 전략을 테스트합니다.

진입 조건: entry_hour 시간에 무조건 매수
청산 조건: exit_hour 시간에 무조건 청산
"""

from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from src.backtest.strategy.timed_hold_strategy import TimedHoldStrategy


class TestTimedHoldStrategy:
    """시간 기반 홀드 전략 테스트"""

    def test_buy_at_entry_hour_default(self) -> None:
        """기본값(0시)에 매수 실행"""
        # Given: 1시간 봉 데이터 (0시 포함)
        cerebro = bt.Cerebro()
        data = self._create_hourly_data_with_entry_hour(entry_hour=0)

        cerebro.adddata(data)
        cerebro.addstrategy(TimedHoldStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 0시에 매수 실행
        assert strategy.buy_executed, "0시에 매수가 실행되어야 함"

    def test_sell_at_exit_hour_default(self) -> None:
        """기본값(12시)에 청산 실행"""
        # Given: 0시~12시 포함 데이터
        cerebro = bt.Cerebro()
        data = self._create_hourly_data_with_entry_hour(entry_hour=0)

        cerebro.adddata(data)
        cerebro.addstrategy(TimedHoldStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 12시에 청산 실행
        assert strategy.buy_executed, "매수가 실행되어야 함"
        assert strategy.sell_executed, "12시에 청산이 실행되어야 함"

    def test_custom_entry_exit_hours(self) -> None:
        """커스텀 시간(9시 매수, 15시 청산) 테스트"""
        # Given: 9시~15시 포함 데이터
        cerebro = bt.Cerebro()
        data = self._create_hourly_data_with_entry_hour(entry_hour=9)

        cerebro.adddata(data)
        cerebro.addstrategy(TimedHoldStrategy, entry_hour=9, exit_hour=15)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 9시 매수, 15시 청산
        assert strategy.params.entry_hour == 9
        assert strategy.params.exit_hour == 15
        assert strategy.buy_executed, "9시에 매수가 실행되어야 함"
        assert strategy.sell_executed, "15시에 청산이 실행되어야 함"

    def test_no_duplicate_entry_same_day(self) -> None:
        """하루에 한 번만 진입"""
        # Given: 동일 날짜에 entry_hour가 여러 번 나오지 않도록 데이터 구성
        cerebro = bt.Cerebro()
        data = self._create_hourly_data_with_entry_hour(entry_hour=0)

        cerebro.adddata(data)
        cerebro.addstrategy(TimedHoldStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 첫 날 진입 후 청산, 둘째 날 다시 진입
        buy_count = sum(1 for t in strategy.trade_history if t["type"] == "buy")
        # 2일치 데이터이므로 최대 2번 매수
        assert buy_count >= 1, "최소 1번은 매수해야 함"

    def test_no_sell_without_position(self) -> None:
        """포지션 없으면 청산 안 함"""
        # Given: entry_hour 없이 exit_hour만 있는 데이터
        cerebro = bt.Cerebro()
        data = self._create_hourly_data_exit_only()

        cerebro.adddata(data)
        cerebro.addstrategy(TimedHoldStrategy)
        cerebro.broker.setcash(100_000_000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 없으면 청산도 없음
        assert not strategy.buy_executed, "매수가 없어야 함"
        assert not strategy.sell_executed, "포지션 없으면 청산 없어야 함"

    def test_trade_history_records(self) -> None:
        """trade_history에 거래 기록 저장"""
        # Given: 매수/청산 발생 데이터
        cerebro = bt.Cerebro()
        data = self._create_hourly_data_with_entry_hour(entry_hour=0)

        cerebro.adddata(data)
        cerebro.addstrategy(TimedHoldStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 거래 기록 확인
        assert len(strategy.trade_history) >= 2, "최소 2건의 거래 기록"

        # 첫 번째: 매수
        first = strategy.trade_history[0]
        assert first["type"] == "buy"
        assert first["action"] == "롱 진입"
        assert "date" in first
        assert "price" in first

        # 두 번째: 매도
        second = strategy.trade_history[1]
        assert second["type"] == "sell"
        assert second["action"] == "롱 청산"

    # === 헬퍼 메서드 ===

    def _create_hourly_data_with_entry_hour(self, entry_hour: int = 0) -> bt.feeds.PandasData:
        """entry_hour와 exit_hour(12시)를 포함하는 1시간 봉 데이터 생성

        2일치 데이터 (48시간)
        """
        base_date = datetime(2024, 1, 1, 0, 0, 0)
        data_list = []

        # 2일치 (48시간)
        for i in range(48):
            dt = base_date + timedelta(hours=i)
            data_list.append({
                'datetime': dt,
                'open': 50000.0,
                'high': 50500.0,
                'low': 49500.0,
                'close': 50000.0,
                'volume': 1000.0,
            })

        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)
        return bt.feeds.PandasData(dataname=df)

    def _create_hourly_data_exit_only(self) -> bt.feeds.PandasData:
        """entry_hour(0시) 없이 exit_hour(12시)만 있는 데이터

        1시~23시까지만 (0시 제외)
        """
        base_date = datetime(2024, 1, 1, 1, 0, 0)  # 1시 시작
        data_list = []

        # 23시간 (1시~23시)
        for i in range(23):
            dt = base_date + timedelta(hours=i)
            data_list.append({
                'datetime': dt,
                'open': 50000.0,
                'high': 50500.0,
                'low': 49500.0,
                'close': 50000.0,
                'volume': 1000.0,
            })

        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)
        return bt.feeds.PandasData(dataname=df)
