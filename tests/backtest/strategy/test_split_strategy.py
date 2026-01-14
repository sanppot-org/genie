"""스플릿 전략 테스트

각 분할은 독립적인 포지션으로 관리:
- 분할 N-1이 -5% 도달 → 분할 N 진입
- 각 분할은 자신의 진입가 기준 +3%에서 개별 익절
"""

import datetime as dt

import backtrader as bt
import pandas as pd
import pytest


class TestSplitStrategy:
    """스플릿 전략 테스트"""

    def test_complex_scenario_split1_triggers_split2_and_split2_takes_profit(self):
        """복합 시나리오: 분할1 진입 → -5%로 분할2 트리거 → 분할2 익절 → 분할1 보유 유지

        시나리오:
        - Day 1: 100원에 분할1 진입
        - Day 2: 95원(-5%)으로 분할2 트리거
        - Day 3: 97.85원(분할2 기준 +3%)으로 분할2 익절
        - 분할1은 여전히 보유 중 (103원에 익절 예정)
        """
        from src.backtest.strategy.split_strategy import SplitStrategy

        # Given: 테스트 데이터 생성
        data = self._create_complex_scenario_data()
        cerebro = bt.Cerebro()
        cerebro.adddata(data)
        cerebro.addstrategy(
            SplitStrategy,
            split_count=3,
            take_profit_rate=0.03,
            trigger_rate=0.05,
        )
        cerebro.broker.setcash(1_000_000)

        # When: 백테스트 실행
        results = cerebro.run()
        strategy = results[0]

        # Then: 상태 검증
        # 분할1, 분할2 진입 확인
        assert strategy.total_entries == 2, "분할1, 분할2 두 번 진입해야 함"

        # 분할2 익절 확인
        assert strategy.total_exits == 1, "분할2만 익절되어야 함"

        # 분할1은 여전히 보유 중
        assert strategy.active_position_count == 1, "분할1은 아직 보유 중이어야 함"

    def _create_complex_scenario_data(self) -> bt.feeds.PandasData:
        """복합 시나리오용 테스트 데이터 생성

        Backtrader는 주문이 다음 bar에 체결되므로 이를 고려한 데이터:
        Day 1: 100원 (분할1 주문)
        Day 2: 100원 (분할1 체결)
        Day 3: 95원 (분할1 -5% → 분할2 주문)
        Day 4: 95원 (분할2 체결)
        Day 5: 97.85원 (분할2 +3% → 분할2 익절 주문)
        Day 6: 98원 (분할2 익절 체결)
        Day 7: 98원 (분할1 여전히 보유)
        """
        dates = [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 2),
            dt.datetime(2024, 1, 3),
            dt.datetime(2024, 1, 4),
            dt.datetime(2024, 1, 5),
            dt.datetime(2024, 1, 6),
            dt.datetime(2024, 1, 7),
        ]

        df = pd.DataFrame({
            "open": [100.0, 100.0, 95.0, 95.0, 97.85, 98.0, 98.0],
            "high": [100.0, 100.0, 95.0, 95.0, 97.85, 98.0, 98.0],
            "low": [100.0, 100.0, 95.0, 95.0, 97.85, 98.0, 98.0],
            "close": [100.0, 100.0, 95.0, 95.0, 97.85, 98.0, 98.0],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000, 1000],
        }, index=dates)

        return bt.feeds.PandasData(dataname=df)
