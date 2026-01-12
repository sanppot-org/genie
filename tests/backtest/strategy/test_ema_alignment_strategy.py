"""EMA 정배열 전략 테스트"""

from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from src.backtest.strategy.ema_alignment_strategy import EmaAlignmentStrategy


class TestEmaAlignmentStrategy:
    """EMA 정배열 전략 테스트

    정배열 조건: EMA20 > EMA40 + 최소 간격 + 최소 기울기
    - 조건 충족 시작 시 매수
    - 정배열 붕괴 시 매도
    """

    def test_buy_when_aligned_with_gap_and_slope(self) -> None:
        """정배열 + 간격 + 기울기 조건 충족 시 매수"""
        # Given: 정배열 + 충분한 간격과 기울기
        cerebro = bt.Cerebro()
        data = self._create_strong_trend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaAlignmentStrategy,
            min_gap=2.0,
            min_slope=1.0,
            slope_period=5,
        )
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 실행
        assert strategy.buy_executed, "강한 추세에서 매수가 실행되어야 함"

    def test_no_buy_when_gap_insufficient(self) -> None:
        """간격 부족 시 매수 안함"""
        # Given: 정배열이지만 간격이 부족한 데이터
        cerebro = bt.Cerebro()
        data = self._create_narrow_gap_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaAlignmentStrategy,
            min_gap=5.0,  # 높은 간격 요구
            min_slope=0.5,
            slope_period=5,
        )
        cerebro.broker.setcash(100_000_000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 미실행
        assert not strategy.buy_executed, "간격 부족 시 매수하지 않아야 함"

    def test_no_buy_when_slope_insufficient(self) -> None:
        """기울기 부족 시 매수 안함"""
        # Given: 정배열이지만 기울기가 부족한 데이터
        cerebro = bt.Cerebro()
        data = self._create_flat_trend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaAlignmentStrategy,
            min_gap=1.0,
            min_slope=5.0,  # 높은 기울기 요구
            slope_period=5,
        )
        cerebro.broker.setcash(100_000_000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 미실행
        assert not strategy.buy_executed, "기울기 부족 시 매수하지 않아야 함"

    def test_sell_when_alignment_breaks(self) -> None:
        """정배열 붕괴 시 매도"""
        # Given: 정배열 → 붕괴
        cerebro = bt.Cerebro()
        data = self._create_trend_break_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaAlignmentStrategy,
            min_gap=2.0,
            min_slope=1.0,
            slope_period=5,
        )
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 후 매도 실행
        assert strategy.buy_executed, "정배열 조건 충족 시 매수가 실행되어야 함"
        assert strategy.sell_executed, "정배열 붕괴 시 매도가 실행되어야 함"

    def test_no_buy_when_not_aligned(self) -> None:
        """정배열이 아닐 때 매수하지 않음"""
        # Given: EMA20 < EMA40 (역배열)
        cerebro = bt.Cerebro()
        data = self._create_downtrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaAlignmentStrategy,
            min_gap=2.0,
            min_slope=1.0,
            slope_period=5,
        )
        cerebro.broker.setcash(100_000_000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 미실행
        assert not strategy.buy_executed, "정배열이 아니면 매수하지 않아야 함"

    # === 헬퍼 메서드 ===

    def _create_strong_trend_data(self) -> bt.feeds.PandasData:
        """강한 상승 추세 데이터 (높은 간격 + 높은 기울기)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 20일: 강한 상승 (일 3% 상승)
        for i in range(20):
            prices.append(50000.0 * (1.03 ** (i + 1)))

        # 5일: 상승 유지
        last_price = prices[-1]
        for i in range(5):
            prices.append(last_price * (1.02 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_narrow_gap_data(self) -> bt.feeds.PandasData:
        """좁은 간격 데이터 (EMA20과 EMA40이 가깝게 유지)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 20일: 아주 완만한 상승 (일 0.3% 상승)
        for i in range(20):
            prices.append(50000.0 * (1.003 ** (i + 1)))

        # 5일: 유지
        last_price = prices[-1]
        for _ in range(5):
            prices.append(last_price)

        return self._prices_to_data(base_date, prices)

    def _create_flat_trend_data(self) -> bt.feeds.PandasData:
        """평탄한 기울기 데이터 (정배열이지만 기울기가 낮음)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 10일: 상승해서 정배열 형성
        for i in range(10):
            prices.append(50000.0 * (1.02 ** (i + 1)))

        # 20일: 횡보 유지 (기울기 낮춤)
        last_price = prices[-1]
        for _ in range(20):
            prices.append(last_price)

        return self._prices_to_data(base_date, prices)

    def _create_trend_break_data(self) -> bt.feeds.PandasData:
        """정배열 후 붕괴 데이터"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 15일: 강한 상승 (정배열 형성 및 매수)
        for i in range(15):
            prices.append(50000.0 * (1.03 ** (i + 1)))

        # 20일: 급락 (정배열 붕괴)
        peak = prices[-1]
        for i in range(20):
            prices.append(peak * (0.96 ** (i + 1)))

        # 5일: 하락 유지
        last_price = prices[-1]
        for _ in range(5):
            prices.append(last_price * 0.98)

        return self._prices_to_data(base_date, prices)

    def _create_downtrend_data(self) -> bt.feeds.PandasData:
        """하락 추세 데이터 (역배열)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보 후 하락
        prices = [50000.0] * 50
        for i in range(20):
            prices.append(50000.0 * (0.98 ** (i + 1)))

        # 5일: 하락 유지
        last_price = prices[-1]
        for _ in range(5):
            prices.append(last_price * 0.99)

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
