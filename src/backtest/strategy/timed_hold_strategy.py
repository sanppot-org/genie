"""시간 기반 홀드 전략

1시간 봉 데이터를 사용하여 지정된 시간에 매수하고, 지정된 시간에 청산하는 전략입니다.
"""

from datetime import date
from typing import Any

import backtrader as bt


class TimedHoldStrategy(bt.Strategy):
    """시간 기반 홀드 전략 (롱 전용)

    지정된 시간에 무조건 매수하고, 지정된 시간에 무조건 청산합니다.
    하루에 한 번만 진입합니다.

    진입 조건: entry_hour 시간에 무조건 매수
    청산 조건: exit_hour 시간에 무조건 청산

    Params:
        entry_hour: 매수 시간 (기본 0, 범위 0~23)
        exit_hour: 청산 시간 (기본 12, 범위 0~23)

    Note:
        시가 체결을 원하면 BacktestBuilder.with_cheat_on_open()을 사용하세요.
        이 경우 next_open()에서 주문이 현재 bar의 시가로 체결됩니다.

    Example:
        >>> cerebro = bt.Cerebro()
        >>> # 기본값: 0시 매수, 12시 청산
        >>> cerebro.addstrategy(TimedHoldStrategy)
        >>> # 커스텀: 9시 매수, 15시 청산
        >>> cerebro.addstrategy(TimedHoldStrategy, entry_hour=9, exit_hour=15)
        >>> cerebro.addsizer(bt.sizers.PercentSizer, percents=95)
        >>> result = cerebro.run()
    """

    params = (
        ("entry_hour", 0),  # 매수 시간 (0~23)
        ("exit_hour", 12),  # 청산 시간 (0~23)
    )

    def __init__(self) -> None:
        """전략 초기화"""
        # 데이터 참조
        self.dataopen = self.datas[0].open
        self.dataclose = self.datas[0].close

        # 주문 추적
        self.order: Any = None

        # 마지막 진입 날짜 (하루에 한 번만 진입)
        self.last_entry_date: date | None = None

        # 테스트용 플래그
        self.buy_executed = False
        self.sell_executed = False

        # 거래 기록 (시각화용)
        self.trade_history: list[dict[str, Any]] = []

    def log(self, txt: str, dt: Any = None) -> None:
        """로깅 함수"""
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f"{dt.isoformat()}, {txt}")

    def notify_order(self, order: Any) -> None:
        """주문 상태 변경 알림"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            trade_datetime = self.datas[0].datetime.datetime(0)
            trade_price = order.executed.price

            if order.isbuy():
                self.buy_executed = True
                self.trade_history.append({
                    "date": trade_datetime,
                    "price": trade_price,
                    "type": "buy",
                    "action": "롱 진입",
                })
                self.log(f"BUY EXECUTED (롱 진입), Price: {trade_price:.2f}")
            elif order.issell():
                self.sell_executed = True
                self.trade_history.append({
                    "date": trade_datetime,
                    "price": trade_price,
                    "type": "sell",
                    "action": "롱 청산",
                })
                self.log(f"SELL EXECUTED (롱 청산), Price: {trade_price:.2f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def next_open(self) -> None:
        """시가 체결용 (cheat_on_open=True 필요)

        이 메서드는 next() 전에 호출되며, 여기서 발생한 주문은
        현재 bar의 시가로 체결됩니다.
        """
        # 대기 중인 주문이 있으면 스킵
        if self.order:
            return

        # 현재 시간 정보 추출
        current_dt = self.datas[0].datetime.datetime(0)
        current_hour = current_dt.hour
        current_date = current_dt.date()

        # === 매수 로직 ===
        # 매수 시간 + 포지션 없음 + 오늘 아직 미진입
        if current_hour == self.params.entry_hour and not self.position:  # type: ignore[attr-defined]
            if self.last_entry_date != current_date:
                self.log(
                    f"BUY CREATE (롱 진입), Open: {self.dataopen[0]:.2f}, "
                    f"Hour: {current_hour}"
                )
                self.order = self.buy()
                self.last_entry_date = current_date

        # === 청산 로직 ===
        # 청산 시간 + 포지션 있음
        elif current_hour == self.params.exit_hour and self.position.size > 0:  # type: ignore[attr-defined]
            self.log(
                f"SELL CREATE (롱 청산), Open: {self.dataopen[0]:.2f}, "
                f"Hour: {current_hour}"
            )
            self.order = self.sell()

    def next(self) -> None:
        """종가 체결용 (기본 동작)

        cheat_on_open=False(기본값)일 때 사용됩니다.
        여기서 발생한 주문은 다음 bar의 시가로 체결됩니다.
        """
        # cheat_on_open=True면 next_open()에서 이미 처리됨
        if self.cerebro.p.cheat_on_open:
            return

        # 대기 중인 주문이 있으면 스킵
        if self.order:
            return

        # 현재 시간 정보 추출
        current_dt = self.datas[0].datetime.datetime(0)
        current_hour = current_dt.hour
        current_date = current_dt.date()

        # === 매수 로직 ===
        # 매수 시간 + 포지션 없음 + 오늘 아직 미진입
        if current_hour == self.params.entry_hour and not self.position:  # type: ignore[attr-defined]
            if self.last_entry_date != current_date:
                self.log(
                    f"BUY CREATE (롱 진입), Close: {self.dataclose[0]:.2f}, "
                    f"Hour: {current_hour}"
                )
                self.order = self.buy()
                self.last_entry_date = current_date

        # === 청산 로직 ===
        # 청산 시간 + 포지션 있음
        elif current_hour == self.params.exit_hour and self.position.size > 0:  # type: ignore[attr-defined]
            self.log(
                f"SELL CREATE (롱 청산), Close: {self.dataclose[0]:.2f}, "
                f"Hour: {current_hour}"
            )
            self.order = self.sell()
