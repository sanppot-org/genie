from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from src.backtest.strategy.morning_afternoon_strategy import MorningAfternoonStrategy


class TestMorningAfternoonStrategy:
    """MorningAfternoonStrategy 테스트"""

    def test_buy_when_conditions_met(self) -> None:
        """조건 만족 시 매수 테스트"""
        # Given: 전일 오후 수익률 > 0, 오전 거래량 < 오후 거래량
        cerebro = bt.Cerebro()

        # 테스트 데이터 생성 (전일 + 당일)
        data = self._create_test_data_with_conditions(
            prev_afternoon_return=5.0,  # 5% 수익
            prev_morning_volume=1000,
            prev_afternoon_volume=2000  # 오후 거래량이 2배
        )

        cerebro.adddata(data)
        cerebro.addstrategy(MorningAfternoonStrategy)
        cerebro.broker.setcash(100000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 주문이 생성되었어야 함
        assert strategy.buy_executed, "조건 만족 시 매수가 실행되어야 함"

    def test_no_buy_when_afternoon_return_negative(self) -> None:
        """전일 오후 수익률이 0 이하일 때 매수하지 않음"""
        # Given: 전일 오후 수익률 <= 0
        cerebro = bt.Cerebro()

        data = self._create_test_data_with_conditions(
            prev_afternoon_return=-2.0,  # -2% 손실
            prev_morning_volume=1000,
            prev_afternoon_volume=2000
        )

        cerebro.adddata(data)
        cerebro.addstrategy(MorningAfternoonStrategy)
        cerebro.broker.setcash(100000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수하지 않음
        assert not strategy.buy_executed, "오후 수익률이 음수면 매수하지 않아야 함"

    def test_no_buy_when_morning_volume_greater(self) -> None:
        """전일 오전 거래량이 오후 거래량 이상일 때 매수하지 않음"""
        # Given: 오전 거래량 >= 오후 거래량
        cerebro = bt.Cerebro()

        data = self._create_test_data_with_conditions(
            prev_afternoon_return=5.0,
            prev_morning_volume=2000,
            prev_afternoon_volume=1000  # 오전이 더 많음
        )

        cerebro.adddata(data)
        cerebro.addstrategy(MorningAfternoonStrategy)
        cerebro.broker.setcash(100000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수하지 않음
        assert not strategy.buy_executed, "오전 거래량이 많으면 매수하지 않아야 함"

    def test_sell_at_morning_close(self) -> None:
        """오전 마지막 봉(11시)에 매도"""
        # Given: 매수 조건 만족 + 포지션 보유
        cerebro = bt.Cerebro()

        data = self._create_test_data_with_conditions(
            prev_afternoon_return=5.0,
            prev_morning_volume=1000,
            prev_afternoon_volume=2000
        )

        cerebro.adddata(data)
        cerebro.addstrategy(MorningAfternoonStrategy)
        cerebro.broker.setcash(100000)

        # When: 백테스트 실행
        result = cerebro.run()
        strategy = result[0]

        # Then: 매수 후 매도 실행
        assert strategy.buy_executed, "매수가 실행되어야 함"
        assert strategy.sell_executed, "11시에 매도가 실행되어야 함"

    def _create_test_data_with_conditions(
            self,
            prev_afternoon_return: float,
            prev_morning_volume: int,
            prev_afternoon_volume: int
    ) -> bt.DataBase:
        """조건에 맞는 테스트 데이터 생성

        Args:
            prev_afternoon_return: 전일 오후 수익률 (%)
            prev_morning_volume: 전일 오전 총 거래량
            prev_afternoon_volume: 전일 오후 총 거래량
        """
        base_date = datetime(2024, 1, 1)
        data_list = []

        # 전일 오전 봉 생성 (0~11시, 12개 봉)
        morning_volume_per_bar = prev_morning_volume / 12
        for hour in range(12):
            dt = base_date.replace(hour=hour)
            data_list.append({
                'datetime': dt,
                'open': 100.0,
                'high': 101.0,
                'low': 99.0,
                'close': 100.0,
                'volume': morning_volume_per_bar
            })

        # 전일 오후 봉 생성 (12~23시, 12개 봉)
        afternoon_volume_per_bar = prev_afternoon_volume / 12

        # 오후 수익률 계산: (종가 - 시가) / 시가 * 100 = prev_afternoon_return
        # 종가 = 시가 * (1 + prev_afternoon_return / 100)
        afternoon_open = 100.0
        afternoon_close = afternoon_open * (1 + prev_afternoon_return / 100)

        for hour in range(12, 24):
            dt = base_date.replace(hour=hour)
            # 첫 봉은 시가, 마지막 봉은 종가, 중간은 선형 보간
            if hour == 12:
                bar_close = afternoon_open
            elif hour == 23:
                bar_close = afternoon_close
            else:
                # 선형 보간
                progress = (hour - 12) / 11
                bar_close = afternoon_open + (afternoon_close - afternoon_open) * progress

            data_list.append({
                'datetime': dt,
                'open': afternoon_open if hour == 12 else data_list[-1]['close'],
                'high': max(afternoon_open, bar_close) + 1.0,
                'low': min(afternoon_open, bar_close) - 1.0,
                'close': bar_close,
                'volume': afternoon_volume_per_bar
            })

        # 당일 오전 봉 생성 (0~11시, 12개 봉)
        next_day = base_date + timedelta(days=1)
        for hour in range(12):
            dt = next_day.replace(hour=hour)
            data_list.append({
                'datetime': dt,
                'open': 105.0,
                'high': 106.0,
                'low': 104.0,
                'close': 105.0,
                'volume': 100.0
            })

        # 당일 오후 봉 생성 (12시, 매도 주문 체결을 위해)
        dt = next_day.replace(hour=12)
        data_list.append({
            'datetime': dt,
            'open': 105.0,
            'high': 106.0,
            'low': 104.0,
            'close': 105.0,
            'volume': 100.0
        })

        # DataFrame 생성
        df = pd.DataFrame(data_list)
        df.set_index('datetime', inplace=True)

        # backtrader DataFeed 생성
        data = bt.feeds.PandasData(dataname=df)

        return data
