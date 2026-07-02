"""무한매수법 전략 테스트 (docs/무한매수법.md 구현)

핵심 시나리오:
1. 첫 매수 → 전반전 분할 매수 누적 → 목표가 도달 시 전량 청산 (사이클 완료)
2. 별지점 도달 시 쿼터매도만 체결 (목표가 미도달 → 사이클 유지)
3. 회차 소진 시 매수 중단 + 매도만 진행
"""

from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from src.backtest.strategy.infinite_buying_strategy import InfiniteBuyingStrategy


class TestInfiniteBuyingStrategy:
    """무한매수법 전략 테스트"""

    def test_accumulate_then_full_take_profit(self) -> None:
        """전반전 분할 매수 누적 → 급등 시 쿼터+지정가 매도로 전량 청산 → 사이클 완료"""
        # Given: 횡보(100) 6일 후 급등(130) 데이터
        cerebro = bt.Cerebro()
        cerebro.adddata(self._to_feed(self._flat_then_rally()))
        cerebro.addstrategy(InfiniteBuyingStrategy, split_count=40)
        cerebro.broker.setcash(100_000_000)

        # When
        strategy = cerebro.run()[0]

        # Then: 매수 누적 후 급등일에 전량 청산되어 사이클이 완료됨
        assert strategy.buy_executed, "첫 매수·전반전 매수가 실행되어야 함"
        buy_count = sum(1 for t in strategy.trade_history if t["type"] == "buy")
        assert buy_count >= 3, f"횡보 구간 동안 분할 매수가 누적되어야 함 (실제: {buy_count}회)"
        assert strategy.sell_executed, "급등 시 매도가 실행되어야 함"
        assert strategy.cycle_count >= 1, "전량 청산으로 사이클이 완료되어야 함"

    def test_quarter_sell_at_star_price(self) -> None:
        """고가가 별지점만 도달(목표가 미도달) 시 쿼터매도만 체결, 사이클 유지"""
        # Given: 매수 후 고가가 별지점(114.25)과 목표가(115) 사이인 데이터
        cerebro = bt.Cerebro()
        cerebro.adddata(self._to_feed(self._touch_star_only()))
        cerebro.addstrategy(InfiniteBuyingStrategy, split_count=40)
        cerebro.broker.setcash(100_000_000)

        # When
        strategy = cerebro.run()[0]

        # Then: 별지점 쿼터매도 체결, 전량 청산은 없음
        assert strategy.sell_executed, "별지점 도달 시 쿼터매도가 체결되어야 함"
        sells = [t for t in strategy.trade_history if t["type"] == "sell"]
        assert any(abs(s["price"] - 114.25) < 0.01 for s in sells), (
            f"쿼터매도는 별지점(114.25) 지정가로 체결되어야 함 (실제: {[s['price'] for s in sells]})"
        )
        assert strategy.cycle_count == 0, "목표가 미도달 시 사이클이 유지되어야 함"
        assert strategy.hold_qty > 0, "쿼터매도 후에도 잔량이 남아야 함"

    def test_exhausted_stops_buying(self) -> None:
        """회차 소진 시 매수 중단 + 매도만 진행 (사이클 미완료)"""
        # Given: 계속 하락하는 데이터 + 분할 4개 (빠른 소진 유도)
        cerebro = bt.Cerebro()
        cerebro.adddata(self._to_feed(self._continuous_decline()))
        cerebro.addstrategy(InfiniteBuyingStrategy, split_count=4)
        cerebro.broker.setcash(100_000_000)

        # When
        strategy = cerebro.run()[0]

        # Then: 분할 소진 후 매수가 멈추고 (자금 한계), 매도(쿼터)만 발생
        assert strategy.buy_executed, "소진 전까지 분할 매수가 실행되어야 함"
        assert strategy.cycle_count == 0, "하락장에서는 사이클이 완료되지 않아야 함"
        assert strategy.hold_qty > 0, "청산 없이 보유가 유지되어야 함"
        # 소진 후 현금이 회당금액의 절반에도 못 미치면 신규 매수 불가
        assert strategy.broker.get_cash() < strategy.per_buy_amount, "자금이 소진 상태여야 함"

    # === 헬퍼 메서드 ===

    def _flat_then_rally(self) -> list[dict]:
        """횡보 100(6일) → 급등: open 100/high 131/close 130 (지정가 매도 체결)"""
        base = datetime(2024, 1, 1)
        rows = [self._candle(base + timedelta(days=i), 100.0) for i in range(6)]
        for i in range(6, 9):
            rows.append({
                "datetime": base + timedelta(days=i),
                "open": 100.0,
                "high": 131.0,
                "low": 99.0,
                "close": 130.0,
                "volume": 1000.0,
            })
        return rows

    def _touch_star_only(self) -> list[dict]:
        """첫 매수(T=1) 직후 고가 114.5 — 별지점(114.25)만 도달, 목표가(115) 미도달

        day0 계획 → day1 첫 매수(T=1, 별지점 114.25) → day2 고가 114.5로 쿼터매도만 체결.
        """
        base = datetime(2024, 1, 1)
        rows = [self._candle(base + timedelta(days=i), 100.0) for i in range(2)]
        rows.append({
            "datetime": base + timedelta(days=2),
            "open": 100.0,
            "high": 114.5,
            "low": 99.0,
            "close": 100.0,
            "volume": 1000.0,
        })
        rows.append(self._candle(base + timedelta(days=3), 100.0))
        return rows

    def _continuous_decline(self) -> list[dict]:
        """100에서 매일 -1씩 하락 (20일) — 분할 4개면 중반에 자금 소진"""
        base = datetime(2024, 1, 1)
        return [self._candle(base + timedelta(days=i), 100.0 - i) for i in range(20)]

    @staticmethod
    def _candle(dt: datetime, price: float) -> dict:
        return {
            "datetime": dt,
            "open": price,
            "high": price + 0.4,
            "low": price - 0.4,
            "close": price,
            "volume": 1000.0,
        }

    @staticmethod
    def _to_feed(rows: list[dict]) -> bt.feeds.PandasData:
        df = pd.DataFrame(rows)
        df.set_index("datetime", inplace=True)
        return bt.feeds.PandasData(dataname=df)
