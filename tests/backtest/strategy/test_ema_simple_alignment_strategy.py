"""EMA 단순 정배열 전략 테스트"""

from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from src.backtest.strategy.ema_simple_alignment_strategy import EmaSimpleAlignmentStrategy


class TestEmaSimpleAlignmentStrategy:
    """EMA 단순 정배열 전략 테스트

    정배열 조건: EMA[0] > EMA[1] > ... > EMA[n] (짧은 기간 > 긴 기간)
    """

    def test_buy_when_aligned_with_default_emas(self) -> None:
        """기본 EMA(5, 20, 40) 정배열 시 매수"""
        # Given: 강한 상승 추세
        cerebro = bt.Cerebro()
        data = self._create_strong_uptrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaSimpleAlignmentStrategy)  # 기본값: (5, 20, 40)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 실행
        assert strategy.buy_executed, "정배열 시 매수가 실행되어야 함"

    def test_buy_when_aligned_with_two_emas(self) -> None:
        """EMA(20, 40) 2개 정배열 시 매수"""
        # Given: 상승 추세
        cerebro = bt.Cerebro()
        data = self._create_strong_uptrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaSimpleAlignmentStrategy,
            ema_periods=(20, 40),  # EMA 2개만 사용
        )
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 실행
        assert strategy.buy_executed, "EMA(20, 40) 정배열 시 매수가 실행되어야 함"

    def test_no_buy_when_not_aligned(self) -> None:
        """정배열이 아닐 때 매수하지 않음"""
        # Given: 하락 추세 (역배열)
        cerebro = bt.Cerebro()
        data = self._create_downtrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaSimpleAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 미실행
        assert not strategy.buy_executed, "정배열이 아니면 매수하지 않아야 함"

    def test_sell_when_alignment_breaks(self) -> None:
        """정배열 붕괴 시 매도"""
        # Given: 상승 후 하락
        cerebro = bt.Cerebro()
        data = self._create_trend_break_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaSimpleAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 후 매도 실행
        assert strategy.buy_executed, "정배열 시 매수가 실행되어야 함"
        assert strategy.sell_executed, "정배열 붕괴 시 매도가 실행되어야 함"

    def test_custom_four_emas(self) -> None:
        """EMA 4개 (10, 20, 50, 100) 정배열 확인"""
        # Given: 강한 상승 추세
        cerebro = bt.Cerebro()
        data = self._create_long_uptrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaSimpleAlignmentStrategy,
            ema_periods=(10, 20, 50, 100),  # EMA 4개
        )
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: EMA 4개 정배열 확인 (인디케이터 개수 검증)
        assert len(strategy.emas) == 4, "EMA 인디케이터 4개가 생성되어야 함"

    def test_short_when_reverse_aligned(self) -> None:
        """역배열 시 숏 진입"""
        # Given: 강한 하락 추세 (역배열 형성)
        cerebro = bt.Cerebro()
        data = self._create_strong_downtrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaSimpleAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 숏 진입 실행
        assert strategy.short_executed, "역배열 시 숏이 실행되어야 함"

    def test_cover_when_reverse_alignment_breaks(self) -> None:
        """역배열 붕괴 시 숏 커버"""
        # Given: 하락 후 상승 (역배열 → 붕괴)
        cerebro = bt.Cerebro()
        data = self._create_reverse_break_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaSimpleAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 숏 진입 후 커버 실행
        assert strategy.short_executed, "역배열 시 숏이 실행되어야 함"
        assert strategy.cover_executed, "역배열 붕괴 시 숏 커버가 실행되어야 함"

    def test_trade_history_records_buy_and_sell(self) -> None:
        """거래 기록이 trade_history에 저장됨"""
        # Given: 상승 후 하락 (매수 → 매도)
        cerebro = bt.Cerebro()
        data = self._create_trend_break_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaSimpleAlignmentStrategy)
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 거래 기록이 저장됨
        assert len(strategy.trade_history) >= 2, "최소 2건의 거래 기록이 있어야 함"

        # 첫 번째 거래는 매수
        first_trade = strategy.trade_history[0]
        assert first_trade["type"] == "buy", "첫 거래는 매수여야 함"
        assert "date" in first_trade
        assert "price" in first_trade
        assert "action" in first_trade

        # 두 번째 거래는 매도
        second_trade = strategy.trade_history[1]
        assert second_trade["type"] == "sell", "두 번째 거래는 매도여야 함"

    # === 헬퍼 메서드 ===

    def _create_strong_uptrend_data(self) -> bt.feeds.PandasData:
        """강한 상승 추세 데이터"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 20일: 강한 상승 (일 3% 상승)
        for i in range(20):
            prices.append(50000.0 * (1.03 ** (i + 1)))

        # 10일: 상승 유지
        last_price = prices[-1]
        for i in range(10):
            prices.append(last_price * (1.02 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_downtrend_data(self) -> bt.feeds.PandasData:
        """하락 추세 데이터"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보 후 하락
        prices = [50000.0] * 50
        for i in range(20):
            prices.append(50000.0 * (0.98 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_strong_downtrend_data(self) -> bt.feeds.PandasData:
        """강한 하락 추세 데이터 (역배열 형성)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 30일: 강한 하락 (일 3% 하락) - 역배열 형성
        for i in range(30):
            prices.append(50000.0 * (0.97 ** (i + 1)))

        # 10일: 하락 유지
        last_price = prices[-1]
        for i in range(10):
            prices.append(last_price * (0.98 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_reverse_break_data(self) -> bt.feeds.PandasData:
        """역배열 후 붕괴 데이터 (하락 → 상승)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 20일: 강한 하락 (역배열 형성)
        for i in range(20):
            prices.append(50000.0 * (0.97 ** (i + 1)))

        # 30일: 급등 (역배열 붕괴)
        bottom = prices[-1]
        for i in range(30):
            prices.append(bottom * (1.04 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_trend_break_data(self) -> bt.feeds.PandasData:
        """정배열 후 붕괴 데이터"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 15일: 강한 상승 (정배열 형성)
        for i in range(15):
            prices.append(50000.0 * (1.03 ** (i + 1)))

        # 20일: 급락 (정배열 붕괴)
        peak = prices[-1]
        for i in range(20):
            prices.append(peak * (0.96 ** (i + 1)))

        return self._prices_to_data(base_date, prices)

    def _create_long_uptrend_data(self) -> bt.feeds.PandasData:
        """장기 상승 추세 데이터 (EMA 100일까지 정배열 형성)"""
        base_date = datetime(2024, 1, 1)

        # 150일: 횡보
        prices = [50000.0] * 150

        # 50일: 강한 상승
        for i in range(50):
            prices.append(50000.0 * (1.02 ** (i + 1)))

        # 20일: 상승 유지
        last_price = prices[-1]
        for i in range(20):
            prices.append(last_price * (1.01 ** (i + 1)))

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
