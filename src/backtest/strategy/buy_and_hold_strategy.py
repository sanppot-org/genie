"""Buy & Hold 백테스트 전략

시작 시점에 전량 매수 후 끝까지 보유합니다.
"""

from typing import Any

import backtrader as bt


class BuyAndHoldStrategy(bt.Strategy):
    """Buy & Hold 전략

    첫 번째 bar에서 전량 매수하고 끝까지 보유합니다.
    매도하지 않습니다.

    Example:
        >>> cerebro = bt.Cerebro()
        >>> cerebro.addstrategy(BuyAndHoldStrategy)
        >>> cerebro.addsizer(bt.sizers.AllInSizer)
        >>> result = cerebro.run()
    """

    def __init__(self) -> None:
        """전략 초기화"""
        self.dataclose = self.datas[0].close
        self.order: Any = None
        self.bought = False

        # 테스트용 플래그
        self.buy_executed = False

    def log(self, txt: str, dt: Any = None) -> None:
        """로깅 함수"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def notify_order(self, order: Any) -> None:
        """주문 상태 변경 알림"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_executed = True
                self.log(f"BUY EXECUTED, Price: {order.executed.price:.2f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def next(self) -> None:
        """매 bar마다 실행되는 전략 로직"""
        # 대기 중인 주문이 있으면 스킵
        if self.order:
            return

        # 첫 번째 bar에서 매수
        if not self.bought and not self.position:
            self.log(f"BUY CREATE, Close: {self.dataclose[0]:.2f}")
            self.order = self.buy()
            self.bought = True
