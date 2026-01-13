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

    # === 간격 필터 테스트 ===

    def test_gap_filter_default_disabled(self) -> None:
        """간격 필터 기본값은 비활성화"""
        # Given: 강한 상승 추세
        cerebro = bt.Cerebro()
        data = self._create_strong_uptrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(EmaSimpleAlignmentStrategy)  # 기본값
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 간격 필터 비활성화 상태
        assert strategy.params.enable_gap_filter is False
        assert strategy.params.min_gap == 2.0  # 기본값
        # 간격 필터 비활성화 시에도 정배열이면 매수
        assert strategy.buy_executed, "간격 필터 비활성화 시 정배열이면 매수해야 함"

    def test_buy_with_gap_filter_when_sufficient_gap(self) -> None:
        """간격 필터 활성화 + 충분한 간격 → 매수"""
        # Given: 강한 상승 추세
        # 참고: EMA는 후행 지표이므로 정배열 형성 직후에는 간격이 매우 작음
        # 정배열 시작 순간의 간격은 0.1% 미만일 수 있음
        cerebro = bt.Cerebro()
        data = self._create_strong_uptrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaSimpleAlignmentStrategy,
            enable_gap_filter=True,
            min_gap=0.05,  # 정배열 형성 직후의 매우 작은 간격도 허용
        )
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 간격 필터 활성화 + 매수 실행
        assert strategy.params.enable_gap_filter is True
        assert strategy.buy_executed, "충분한 간격에서 매수가 실행되어야 함"

    def test_no_buy_with_gap_filter_when_insufficient_gap(self) -> None:
        """간격 필터 활성화 + 불충분한 간격 → 매수 안함"""
        # Given: 약한 상승 추세 (EMA 간격 < 5%)
        cerebro = bt.Cerebro()
        data = self._create_weak_uptrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaSimpleAlignmentStrategy,
            enable_gap_filter=True,
            min_gap=5.0,  # 5% 이상 간격 요구 (약한 추세는 통과 못함)
        )
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 간격 필터 미통과로 매수 안함
        assert strategy.params.enable_gap_filter is True
        assert not strategy.buy_executed, "불충분한 간격에서는 매수하지 않아야 함"

    def test_short_with_gap_filter_when_sufficient_gap(self) -> None:
        """간격 필터 활성화 + 역배열 + 충분한 간격 → 숏"""
        # Given: 강한 하락 추세 (역배열, EMA 간격 충분)
        # 참고: EMA는 후행 지표이므로 역배열 형성 직후에는 간격이 매우 작음
        cerebro = bt.Cerebro()
        data = self._create_strong_downtrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaSimpleAlignmentStrategy,
            enable_gap_filter=True,
            min_gap=0.05,  # 역배열 형성 직후의 매우 작은 간격도 허용
        )
        cerebro.broker.setcash(100_000_000)
        cerebro.addsizer(bt.sizers.FixedSize, stake=1)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 간격 필터 활성화 + 숏 실행
        assert strategy.short_executed, "충분한 간격의 역배열에서 숏이 실행되어야 함"

    def test_gap_filter_custom_min_gap(self) -> None:
        """간격 필터 min_gap 커스텀 설정"""
        # Given
        cerebro = bt.Cerebro()
        data = self._create_strong_uptrend_data()

        cerebro.adddata(data)
        cerebro.addstrategy(
            EmaSimpleAlignmentStrategy,
            enable_gap_filter=True,
            min_gap=3.5,  # 커스텀 값
        )
        cerebro.broker.setcash(100_000_000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 파라미터 확인
        assert strategy.params.enable_gap_filter is True
        assert strategy.params.min_gap == 3.5

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

    def _create_weak_uptrend_data(self) -> bt.feeds.PandasData:
        """약한 상승 추세 데이터 (횡보에 가까움)"""
        base_date = datetime(2024, 1, 1)

        # 50일: 횡보
        prices = [50000.0] * 50

        # 30일: 매우 약한 상승 (일 0.3% 상승) - 횡보에 가까움
        for i in range(30):
            prices.append(50000.0 * (1.003 ** (i + 1)))

        # 20일: 횡보 유지
        last_price = prices[-1]
        for i in range(20):
            # 약간의 노이즈 추가
            noise = 1.001 if i % 2 == 0 else 0.999
            prices.append(last_price * noise)
            last_price = prices[-1]

        return self._prices_to_data(base_date, prices)

    def _prices_to_data(
            self, base_date: datetime, prices: list[float],
            volatility: float = 0.03
    ) -> bt.feeds.PandasData:
        """가격 리스트를 backtrader 데이터로 변환

        Args:
            base_date: 시작 날짜
            prices: 종가 리스트
            volatility: 변동성 (high/low 범위), 기본값 3%
        """
        import random
        random.seed(42)  # 재현성을 위해 시드 고정

        data_list = []
        for i, price in enumerate(prices):
            dt = base_date + timedelta(days=i)
            # 각 bar마다 약간의 노이즈 추가
            noise = random.uniform(-0.005, 0.005)
            high_noise = random.uniform(0, 0.01)
            low_noise = random.uniform(0, 0.01)

            data_list.append({
                'datetime': dt,
                'open': price * (1 + noise),
                'high': price * (1 + volatility + high_noise),
                'low': price * (1 - volatility - low_noise),
                'close': price,
                'volume': 1000.0,
            })

        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)

        return bt.feeds.PandasData(dataname=df)
