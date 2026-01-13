"""변동성 돌파 전략 (Larry Williams)

전일 변동폭(Range)을 기반으로 돌파 포인트를 계산하여 진입하는 단기 트레이딩 전략입니다.
"""

from typing import Any

import backtrader as bt


class VolatilityBreakoutStrategy(bt.Strategy):
    """변동성 돌파 전략 (롱 전용)

    Larry Williams의 단기 트레이딩 전략으로, 전일 변동폭을 기반으로
    당일 돌파 포인트를 계산합니다.

    진입 조건: 종가 > 시가 + (전일 Range × K)
    청산: 진입 다음 bar에서 포지션 종료

    Params:
        k_value: 돌파 계수 (기본 0.5)

    Example:
        >>> cerebro = bt.Cerebro()
        >>> cerebro.addstrategy(VolatilityBreakoutStrategy, k_value=0.5)
        >>> cerebro.addsizer(bt.sizers.PercentSizer, percents=95)
        >>> result = cerebro.run()
    """

    params = (
        ("k_value", 0.5),  # 돌파 계수
    )

    def __init__(self) -> None:
        """전략 초기화"""
        # 데이터 참조
        self.dataopen = self.datas[0].open
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.dataclose = self.datas[0].close

        # 주문 추적
        self.order: Any = None

        # 진입 bar 추적 (다음 bar에서 청산하기 위함)
        self.entry_bar: int = -1

        # 테스트용 플래그
        self.buy_executed = False
        self.sell_executed = False

        # 거래 기록 (시각화용)
        self.trade_history: list[dict[str, Any]] = []

    def _calculate_range(self) -> float:
        """전일 Range 계산 (High - Low)

        Returns:
            전일 고가 - 전일 저가
        """
        return self.datahigh[-1] - self.datalow[-1]

    def _get_breakout_price(self) -> float:
        """돌파가 계산

        Returns:
            당일 시가 + (전일 Range × K)
        """
        return self.dataopen[0] + (self._calculate_range() * self.params.k_value)  # type: ignore[attr-defined]

    def _is_breakout(self) -> bool:
        """돌파 확인

        Returns:
            True if 종가 > 돌파가
        """
        return self.dataclose[0] > self._get_breakout_price()

    def log(self, txt: str, dt: Any = None) -> None:
        """로깅 함수"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def notify_order(self, order: Any) -> None:
        """주문 상태 변경 알림"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            trade_date = self.datas[0].datetime.date(0)
            trade_price = order.executed.price

            if order.isbuy():
                self.buy_executed = True
                self.trade_history.append({
                    "date": trade_date,
                    "price": trade_price,
                    "type": "buy",
                    "action": "롱 진입",
                })
                self.log(f"BUY EXECUTED (롱 진입), Price: {trade_price:.2f}")
            elif order.issell():
                self.sell_executed = True
                self.trade_history.append({
                    "date": trade_date,
                    "price": trade_price,
                    "type": "sell",
                    "action": "롱 청산",
                })
                self.log(f"SELL EXECUTED (롱 청산), Price: {trade_price:.2f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def next(self) -> None:
        """매 bar마다 실행되는 전략 로직"""
        # 대기 중인 주문이 있으면 스킵
        if self.order:
            return

        # 최소 2일치 데이터 필요 (전일 Range 계산용)
        if len(self) < 2:
            return

        # === 청산 로직 (진입 다음 bar에서 청산) ===
        if self.position.size > 0:
            # 진입한 bar 이후라면 청산
            if len(self) > self.entry_bar:
                self.log(f"SELL CREATE (롱 청산), Close: {self.dataclose[0]:.2f}")
                self.order = self.sell()
            return  # 포지션 있으면 신규 진입 안함

        # === 진입 로직 ===
        if self._is_breakout():
            breakout_price = self._get_breakout_price()
            self.log(
                f"BUY CREATE (롱 진입), Close: {self.dataclose[0]:.2f}, "
                f"Breakout: {breakout_price:.2f}"
            )
            self.order = self.buy()
            self.entry_bar = len(self)
