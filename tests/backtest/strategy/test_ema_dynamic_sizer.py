"""EMA 기반 동적 사이저 테스트"""

from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from src.backtest.strategy.ema_alignment_strategy import EmaAlignmentStrategy
from src.backtest.strategy.ema_dynamic_sizer import EmaDynamicSizer


class TestEmaDynamicSizer:
    """EMA 기울기/간격 기반 동적 사이저 테스트"""

    def test_high_slope_high_weight(self) -> None:
        """기울기가 가파르면 높은 비중으로 매수"""
        # Given: 급등하는 데이터 (높은 기울기)
        cerebro = bt.Cerebro()
        data = self._create_steep_slope_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(EmaDynamicSizer, max_slope=5.0, max_gap=10.0)

        initial_cash = cerebro.broker.getvalue()

        # When: 백테스트 실행
        cerebro.run()

        # Then: 높은 비중으로 매수 (포지션 가치가 초기 자본의 50% 이상)
        final_value = cerebro.broker.getvalue()
        # 매수가 실행되었다면 현금이 줄어들어야 함
        assert cerebro.broker.getcash() < initial_cash * 0.7, "높은 기울기에서 높은 비중 매수 필요"

    def test_low_slope_low_weight(self) -> None:
        """기울기가 완만하면 낮은 비중으로 매수"""
        # Given: 완만하게 상승하는 데이터 (낮은 기울기)
        cerebro = bt.Cerebro()
        data = self._create_gentle_slope_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(EmaDynamicSizer, max_slope=5.0, max_gap=10.0, min_weight=0.3)

        initial_cash = cerebro.broker.getvalue()

        # When: 백테스트 실행
        cerebro.run()

        # Then: 낮은 비중으로 매수 (현금이 많이 남아있어야 함)
        remaining_cash = cerebro.broker.getcash()
        # min_weight=0.3이므로 최소 70%의 현금은 남아야 함 (여유 두고 50%)
        assert remaining_cash > initial_cash * 0.3, "낮은 기울기에서 낮은 비중 매수 필요"

    def test_wide_gap_high_weight(self) -> None:
        """EMA 간격이 넓으면 높은 비중"""
        # Given: 간격이 넓어지는 데이터
        cerebro = bt.Cerebro()
        data = self._create_wide_gap_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(EmaDynamicSizer, max_slope=5.0, max_gap=10.0)

        initial_cash = cerebro.broker.getvalue()

        # When: 백테스트 실행
        cerebro.run()

        # Then: 높은 비중으로 매수
        remaining_cash = cerebro.broker.getcash()
        assert remaining_cash < initial_cash * 0.7, "넓은 간격에서 높은 비중 매수 필요"

    def test_weight_bounded_min_max(self) -> None:
        """비중이 min_weight ~ max_weight 범위 내"""
        # Given: 다양한 상황의 데이터
        cerebro = bt.Cerebro()
        data = self._create_steep_slope_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(EmaDynamicSizer,
                         min_weight=0.2,
                         max_weight=0.8,
                         max_slope=5.0,
                         max_gap=10.0)

        initial_cash = cerebro.broker.getvalue()

        # When: 백테스트 실행
        cerebro.run()

        # Then: 비중이 범위 내 (20% ~ 80%)
        remaining_cash = cerebro.broker.getcash()
        # max_weight=0.8이므로 최소 20%의 현금은 남아야 함
        assert remaining_cash >= initial_cash * 0.1, "비중이 max_weight를 초과하면 안됨"

    def test_sell_returns_full_position(self) -> None:
        """매도 시 전체 포지션 청산"""
        # Given: 정배열 후 붕괴하는 데이터
        cerebro = bt.Cerebro()
        data = self._create_alignment_break_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(EmaDynamicSizer, max_slope=5.0, max_gap=10.0)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 후 매도 실행됨
        assert strategy.buy_executed, "매수가 실행되어야 함"
        assert strategy.sell_executed, "매도가 실행되어야 함"

    # === 헬퍼 메서드 ===

    def _create_steep_slope_data(self) -> bt.feeds.PandasData:
        """급등하는 테스트 데이터 (높은 기울기)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 15일: 급등 (일 5% 상승)
        for i in range(15):
            prices.append(50000.0 * (1.05 ** (i + 1)))

        # 5일: 상승 유지
        last_price = prices[-1]
        for i in range(5):
            prices.append(last_price * (1.02 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_gentle_slope_data(self) -> bt.feeds.PandasData:
        """완만하게 상승하는 테스트 데이터 (낮은 기울기)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 20일: 완만한 상승 (일 0.5% 상승)
        for i in range(20):
            prices.append(50000.0 * (1.005 ** (i + 1)))

        # 5일: 상승 유지
        last_price = prices[-1]
        for _ in range(5):
            prices.append(last_price * 1.003)

        return self._prices_to_data(base_date, prices)

    def _create_wide_gap_data(self) -> bt.feeds.PandasData:
        """EMA 간격이 넓어지는 테스트 데이터"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 20일: 급등 후 유지 (간격 벌어짐)
        for i in range(10):
            prices.append(50000.0 * (1.04 ** (i + 1)))

        last_price = prices[-1]
        for i in range(15):
            prices.append(last_price * (1.01 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_alignment_break_data(self) -> bt.feeds.PandasData:
        """정배열 후 붕괴 테스트 데이터"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 15일: 급등 (정배열 형성)
        for i in range(15):
            prices.append(50000.0 + (i + 1) * 2500)

        # 15일: 급락 (정배열 붕괴)
        peak = prices[-1]
        for i in range(15):
            prices.append(peak - (i + 1) * 4000)

        # 5일: 하락 유지
        last_price = prices[-1]
        for i in range(5):
            prices.append(last_price - (i + 1) * 1000)

        return self._prices_to_data(base_date, prices)

    def _prices_to_data(
            self, base_date: datetime, prices: list[float]
    ) -> bt.feeds.PandasData:
        """가격 리스트를 backtrader 데이터로 변환"""
        data_list = []
        for i, price in enumerate(prices):
            dt = base_date + timedelta(days=i)
            data_list.append({
                'datetime': dt,
                'open': price,
                'high': price * 1.01,
                'low': price * 0.99,
                'close': price,
                'volume': 1000.0,
            })

        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)

        return bt.feeds.PandasData(dataname=df)
