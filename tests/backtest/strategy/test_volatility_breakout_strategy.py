"""변동성 돌파 전략 테스트

Larry Williams의 변동성 돌파 전략을 테스트합니다.

진입 조건: 종가 > 시가 + (전일 Range × K)
청산: 진입 다음 bar에서 포지션 종료
"""

from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from src.backtest.strategy.volatility_breakout_strategy import VolatilityBreakoutStrategy


class TestVolatilityBreakoutStrategy:
    """변동성 돌파 전략 테스트"""

    def test_buy_when_breakout_up(self) -> None:
        """상단 돌파 시 매수"""
        # Given: 상단 돌파 데이터
        cerebro = bt.Cerebro()
        data = self._create_breakout_up_data()

        cerebro.adddata(data)
        cerebro.addstrategy(VolatilityBreakoutStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 실행
        assert strategy.buy_executed, "상단 돌파 시 매수가 실행되어야 함"

    def test_sell_next_bar_after_long_entry(self) -> None:
        """롱 진입 다음 bar에서 청산"""
        # Given: 돌파 후 충분한 데이터
        cerebro = bt.Cerebro()
        data = self._create_breakout_up_data()

        cerebro.adddata(data)
        cerebro.addstrategy(VolatilityBreakoutStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 후 매도 실행
        assert strategy.buy_executed, "매수가 실행되어야 함"
        assert strategy.sell_executed, "다음 bar에서 매도가 실행되어야 함"

    def test_no_buy_when_no_breakout(self) -> None:
        """돌파 미달 시 매수 안함"""
        # Given: 돌파 없는 횡보 데이터
        cerebro = bt.Cerebro()
        data = self._create_no_breakout_data()

        cerebro.adddata(data)
        cerebro.addstrategy(VolatilityBreakoutStrategy)
        cerebro.broker.setcash(100_000_000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 미실행
        assert not strategy.buy_executed, "돌파 미달 시 매수하지 않아야 함"

    def test_custom_k_value(self) -> None:
        """K값 커스텀 설정 (낮은 K = 더 쉬운 돌파)"""
        # Given: 약한 돌파 데이터 + 낮은 K값
        cerebro = bt.Cerebro()
        data = self._create_weak_breakout_data()

        cerebro.adddata(data)
        cerebro.addstrategy(VolatilityBreakoutStrategy, k_value=0.3)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: K=0.3으로 돌파 성공
        assert strategy.params.k_value == 0.3
        assert strategy.buy_executed, "낮은 K값에서 돌파 성공해야 함"

    def test_trade_history_records(self) -> None:
        """trade_history에 거래 기록 저장"""
        # Given: 돌파 매수 후 청산
        cerebro = bt.Cerebro()
        data = self._create_breakout_up_data()

        cerebro.adddata(data)
        cerebro.addstrategy(VolatilityBreakoutStrategy)
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

    def _create_breakout_up_data(self) -> bt.feeds.PandasData:
        """상단 돌파 데이터

        전일: Range = 1000 (High=51000, Low=50000)
        당일: 시가=50500, 종가=51100 (> 50500 + 1000*0.5 = 51000)
        """
        base_date = datetime(2024, 1, 1)
        data_list = []

        # 초기 10일: 횡보
        for i in range(10):
            data_list.append({
                'datetime': base_date + timedelta(days=i),
                'open': 50000.0,
                'high': 50500.0,
                'low': 49500.0,
                'close': 50000.0,
                'volume': 1000.0,
            })

        # 11일차: Range 형성 (High=51000, Low=50000)
        data_list.append({
            'datetime': base_date + timedelta(days=10),
            'open': 50000.0,
            'high': 51000.0,
            'low': 50000.0,
            'close': 50500.0,
            'volume': 1000.0,
        })

        # 12일차: 돌파 (종가 > 시가 + Range*0.5)
        # Range=1000, 시가=50500, 돌파가=51000
        # 종가=51100 > 51000 -> 돌파
        data_list.append({
            'datetime': base_date + timedelta(days=11),
            'open': 50500.0,
            'high': 51200.0,
            'low': 50400.0,
            'close': 51100.0,
            'volume': 1000.0,
        })

        # 13일차 이후: 청산용
        for i in range(5):
            data_list.append({
                'datetime': base_date + timedelta(days=12 + i),
                'open': 51000.0,
                'high': 51500.0,
                'low': 50500.0,
                'close': 51000.0,
                'volume': 1000.0,
            })

        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)
        return bt.feeds.PandasData(dataname=df)

    def _create_no_breakout_data(self) -> bt.feeds.PandasData:
        """돌파 없는 횡보 데이터"""
        base_date = datetime(2024, 1, 1)
        data_list = []

        # 20일: 일정한 횡보 (돌파 조건 미충족)
        for i in range(20):
            data_list.append({
                'datetime': base_date + timedelta(days=i),
                'open': 50000.0,
                'high': 50200.0,  # Range = 400
                'low': 49800.0,
                'close': 50000.0,  # 종가 = 시가 (돌파 없음)
                'volume': 1000.0,
            })

        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)
        return bt.feeds.PandasData(dataname=df)

    def _create_weak_breakout_data(self) -> bt.feeds.PandasData:
        """약한 돌파 데이터 (K=0.5에서는 돌파 실패, K=0.3에서는 성공)"""
        base_date = datetime(2024, 1, 1)
        data_list = []

        # 10일: 횡보
        for i in range(10):
            data_list.append({
                'datetime': base_date + timedelta(days=i),
                'open': 50000.0,
                'high': 50500.0,
                'low': 49500.0,
                'close': 50000.0,
                'volume': 1000.0,
            })

        # 11일차: Range=1000
        data_list.append({
            'datetime': base_date + timedelta(days=10),
            'open': 50000.0,
            'high': 51000.0,
            'low': 50000.0,
            'close': 50500.0,
            'volume': 1000.0,
        })

        # 12일차: 약한 돌파
        # K=0.5: 돌파가=50500+500=51000, 종가=50850 -> 실패
        # K=0.3: 돌파가=50500+300=50800, 종가=50850 -> 성공
        data_list.append({
            'datetime': base_date + timedelta(days=11),
            'open': 50500.0,
            'high': 50900.0,
            'low': 50400.0,
            'close': 50850.0,
            'volume': 1000.0,
        })

        # 청산용
        for i in range(5):
            data_list.append({
                'datetime': base_date + timedelta(days=12 + i),
                'open': 50800.0,
                'high': 51000.0,
                'low': 50600.0,
                'close': 50800.0,
                'volume': 1000.0,
            })

        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)
        return bt.feeds.PandasData(dataname=df)
