from typing import Any

import backtrader as bt


class SimpleStrategy(bt.Strategy):
    """Simple Moving Average Strategy"""

    params = (
        ("ma_period", 15),
    )

    def log(self, txt: str, dt: Any = None) -> None:  # type: ignore[misc]
        """Logging function"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def __init__(self) -> None:
        # Keep reference to close price
        self.dataclose = self.datas[0].close

        # Add Simple Moving Average indicator
        self.sma = bt.indicators.MovingAverageSimple(
            self.datas[0], period=self.params.ma_period  # type: ignore[attr-defined]
        )

        # Track pending orders
        self.order = None

    def notify_order(self, order: Any) -> None:  # type: ignore[misc]
        """Notification of order status changes"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f"BUY EXECUTED, Price: {order.executed.price:.2f}")
            elif order.issell():
                self.log(f"SELL EXECUTED, Price: {order.executed.price:.2f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def next(self) -> None:
        """Strategy logic executed for each bar"""
        self.log(f"Close: {self.dataclose[0]:.2f}")

        # Skip if order is pending
        if self.order:
            return

        # If not in position
        if not self.position and self.dataclose[0] > self.sma[0]:
            self.log(f"BUY CREATE, {self.dataclose[0]:.2f}")
            self.order = self.buy()

        # If in position
        elif self.dataclose[0] < self.sma[0]:
            self.log(f"SELL CREATE, {self.dataclose[0]:.2f}")
            self.order = self.sell()
