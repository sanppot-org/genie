"""EMA 정배열 백테스트 전략

일봉 기준 EMA(5, 20, 40)를 사용하여 정배열 + 간격/기울기 조건 충족 시 매수,
정배열 붕괴 시 매도합니다.
"""

from typing import Any

import backtrader as bt


class EmaAlignmentStrategy(bt.Strategy):
    """EMA 정배열 전략

    EMA(5, 20, 40)를 사용하여 정배열 + 최소 간격/기울기 조건 충족 시 매수,
    정배열 붕괴 시 매도합니다.

    진입 조건:
        1. 정배열: EMA5 > EMA20 > EMA40
        2. 최소 간격: (EMA20 - EMA40) / EMA40 >= min_gap%
        3. 최소 기울기: 평균 기울기 >= min_slope%
        4. 이전 bar에서는 조건 미충족 (진입 시작 감지)

    청산 조건:
        - 정배열 붕괴: EMA5 <= EMA20 또는 EMA20 <= EMA40

    Params:
        ema_short: 단기 EMA 기간 (기본: 5)
        ema_mid: 중기 EMA 기간 (기본: 20)
        ema_long: 장기 EMA 기간 (기본: 40)
        slope_period: 기울기 계산 기간 (기본: 5)
        min_gap: 최소 간격 % (기본: 2.0)
        min_slope: 최소 기울기 % (기본: 1.0)

    Example:
        >>> cerebro = bt.Cerebro()
        >>> cerebro.addstrategy(EmaAlignmentStrategy, min_gap=2.0, min_slope=1.0)
        >>> cerebro.addsizer(bt.sizers.AllInSizer)
        >>> result = cerebro.run()
    """

    params = (
        ("ema_short", 5),
        ("ema_mid", 20),
        ("ema_long", 40),
        ("slope_period", 5),
        ("min_gap", 2.0),
        ("min_slope", 1.0),
    )

    def __init__(self) -> None:
        """전략 초기화"""
        # 종가 참조
        self.dataclose = self.datas[0].close

        # EMA 인디케이터
        self.ema_short = bt.indicators.EMA(
            self.datas[0], period=self.params.ema_short  # type: ignore[attr-defined]
        )
        self.ema_mid = bt.indicators.EMA(
            self.datas[0], period=self.params.ema_mid  # type: ignore[attr-defined]
        )
        self.ema_long = bt.indicators.EMA(
            self.datas[0], period=self.params.ema_long  # type: ignore[attr-defined]
        )

        # 주문 추적
        self.order: Any = None

        # 이전 진입 조건 상태 (진입 "시작" 감지용)
        self.was_entry_condition = False

        # 테스트용 플래그
        self.buy_executed = False
        self.sell_executed = False

    def _is_aligned(self) -> bool:
        """현재 정배열 상태 확인

        Returns:
            True if EMA5 > EMA20 > EMA40
        """
        return bool(
            self.ema_short[0] > self.ema_mid[0] > self.ema_long[0]
        )

    def _get_gap_ratio(self) -> float:
        """EMA 간격 비율 계산 (%)

        Returns:
            (EMA20 - EMA40) / EMA40 * 100
        """
        if self.ema_long[0] == 0:
            return 0.0
        return (self.ema_mid[0] - self.ema_long[0]) / self.ema_long[0] * 100

    def _get_avg_slope(self) -> float:
        """평균 기울기 계산 (%)

        Returns:
            EMA20과 EMA40의 평균 기울기 (slope_period 기간)
        """
        slope_period = self.params.slope_period  # type: ignore[attr-defined]

        try:
            ema_mid_prev = self.ema_mid[-slope_period]
            ema_long_prev = self.ema_long[-slope_period]
        except IndexError:
            return 0.0

        if ema_mid_prev == 0 or ema_long_prev == 0:
            return 0.0

        slope_mid = (self.ema_mid[0] - ema_mid_prev) / ema_mid_prev * 100
        slope_long = (self.ema_long[0] - ema_long_prev) / ema_long_prev * 100

        return (slope_mid + slope_long) / 2

    def _is_entry_condition(self) -> bool:
        """진입 조건 충족 여부 확인

        Returns:
            True if 정배열 + 최소 간격 + 최소 기울기
        """
        if not self._is_aligned():
            return False

        gap_ratio = self._get_gap_ratio()
        avg_slope = self._get_avg_slope()

        min_gap = self.params.min_gap  # type: ignore[attr-defined]
        min_slope = self.params.min_slope  # type: ignore[attr-defined]

        return gap_ratio >= min_gap and avg_slope >= min_slope

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
            elif order.issell():
                self.sell_executed = True
                self.log(f"SELL EXECUTED, Price: {order.executed.price:.2f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def next(self) -> None:
        """매 bar마다 실행되는 전략 로직"""
        # 대기 중인 주문이 있으면 스킵
        if self.order:
            return

        is_entry_condition = self._is_entry_condition()

        # 매수 조건: 포지션 없음 + 진입 조건 시작
        if not self.position and is_entry_condition and not self.was_entry_condition:
            self.log(f"BUY CREATE, Close: {self.dataclose[0]:.2f}")
            self.log(
                f"EMA5: {self.ema_short[0]:.2f}, "
                f"EMA20: {self.ema_mid[0]:.2f}, "
                f"EMA40: {self.ema_long[0]:.2f}, "
                f"Gap: {self._get_gap_ratio():.2f}%, "
                f"Slope: {self._get_avg_slope():.2f}%"
            )
            self.order = self.buy()

        # 매도 조건: 포지션 있음 + 정배열 붕괴
        elif self.position and not self._is_aligned():
            self.log(f"SELL CREATE, Close: {self.dataclose[0]:.2f}")
            self.log(
                f"EMA5: {self.ema_short[0]:.2f}, "
                f"EMA20: {self.ema_mid[0]:.2f}, "
                f"EMA40: {self.ema_long[0]:.2f}"
            )
            self.order = self.sell()

        # 상태 업데이트
        self.was_entry_condition = is_entry_condition
