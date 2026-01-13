"""EMA 단순 정배열/역배열 양방향 전략

일봉 기준 EMA 정배열 시 롱, 역배열 시 숏을 잡는 양방향 전략입니다.
"""

from typing import Any

import backtrader as bt


class EmaSimpleAlignmentStrategy(bt.Strategy):
    """EMA 단순 정배열/역배열 양방향 전략

    지정된 EMA들의 정배열 시 롱, 역배열 시 숏을 잡습니다.

    정배열 조건: EMA[0] > EMA[1] > ... > EMA[n] (짧은 기간 > 긴 기간)
    역배열 조건: EMA[0] < EMA[1] < ... < EMA[n] (짧은 기간 < 긴 기간)

    롱 진입: 정배열 시작 (이전 bar 비정배열 → 현재 bar 정배열)
    롱 청산: 정배열 붕괴
    숏 진입: 역배열 시작 (이전 bar 비역배열 → 현재 bar 역배열)
    숏 커버: 역배열 붕괴

    Params:
        ema_periods: EMA 기간 튜플 (오름차순, 예: (5, 20, 40))

    Example:
        >>> cerebro = bt.Cerebro()
        >>> # 기본값: EMA(5, 20, 40)
        >>> cerebro.addstrategy(EmaSimpleAlignmentStrategy)
        >>> # EMA 2개만 사용: EMA(20, 40)
        >>> cerebro.addstrategy(EmaSimpleAlignmentStrategy, ema_periods=(20, 40))
        >>> cerebro.addsizer(bt.sizers.AllInSizer)
        >>> result = cerebro.run()
    """

    params = (
        ("ema_periods", (5, 20, 40)),
        ("enable_long", True),  # 롱 포지션 활성화
        ("enable_short", True),  # 숏 포지션 활성화
        # 간격 필터 관련 파라미터
        ("enable_gap_filter", False),  # 간격 필터 활성화 (기본값: 비활성화)
        ("min_gap", 2.0),  # 최소 간격 (%, EMA20과 EMA40의 차이)
    )

    def __init__(self) -> None:
        """전략 초기화"""
        # 종가 참조
        self.dataclose = self.datas[0].close

        # 동적 EMA 인디케이터 생성
        self.emas = [
            bt.indicators.EMA(self.datas[0], period=period)
            for period in self.params.ema_periods  # type: ignore[attr-defined]
        ]

        # 주문 추적
        self.order: Any = None

        # 이전 상태 추적
        self.was_aligned = False
        self.was_reverse_aligned = False

        # 테스트용 플래그
        self.buy_executed = False
        self.sell_executed = False
        self.short_executed = False
        self.cover_executed = False

        # 거래 기록 (시각화용)
        self.trade_history: list[dict[str, Any]] = []

    def _is_aligned(self) -> bool:
        """현재 정배열 상태 확인

        Returns:
            True if EMA[0] > EMA[1] > ... > EMA[n]
        """
        for i in range(len(self.emas) - 1):
            if self.emas[i][0] <= self.emas[i + 1][0]:
                return False
        return True

    def _is_reverse_aligned(self) -> bool:
        """현재 역배열 상태 확인

        Returns:
            True if EMA[0] < EMA[1] < ... < EMA[n]
        """
        for i in range(len(self.emas) - 1):
            if self.emas[i][0] >= self.emas[i + 1][0]:
                return False
        return True

    def _get_gap_ratio(self) -> float:
        """EMA 간격 비율 계산 (%)

        EMA 기간이 오름차순(5,20,40)이므로:
        - emas[1] = EMA(20)
        - emas[2] = EMA(40)

        Returns:
            (EMA20 - EMA40) / EMA40 * 100
        """
        if len(self.emas) < 3:
            return 0.0
        ema_mid = self.emas[1][0]  # EMA(20)
        ema_long = self.emas[2][0]  # EMA(40)
        if ema_long == 0:
            return 0.0
        return (ema_mid - ema_long) / ema_long * 100

    def _has_sufficient_gap(self) -> bool:
        """간격 필터 조건 확인

        Returns:
            True if 필터 비활성화 or |간격| >= min_gap
        """
        if not self.params.enable_gap_filter:  # type: ignore[attr-defined]
            return True  # 필터 비활성화 시 항상 True
        return abs(self._get_gap_ratio()) >= self.params.min_gap  # type: ignore[attr-defined]

    def _log_emas(self) -> None:
        """EMA 값 로깅"""
        ema_strs = [
            f"EMA{period}: {ema[0]:.2f}"
            for period, ema in zip(
                self.params.ema_periods,  # type: ignore[attr-defined]
                self.emas,
                strict=True
            )
        ]
        self.log(", ".join(ema_strs))

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
                if self.position.size > 0:
                    self.buy_executed = True
                    self.trade_history.append({
                        "date": trade_date,
                        "price": trade_price,
                        "type": "buy",
                        "action": "롱 진입",
                    })
                    self.log(f"BUY EXECUTED (롱 진입), Price: {trade_price:.2f}")
                else:
                    self.cover_executed = True
                    self.trade_history.append({
                        "date": trade_date,
                        "price": trade_price,
                        "type": "buy",
                        "action": "숏 커버",
                    })
                    self.log(f"BUY EXECUTED (숏 커버), Price: {trade_price:.2f}")
            elif order.issell():
                if self.position.size < 0:
                    self.short_executed = True
                    self.trade_history.append({
                        "date": trade_date,
                        "price": trade_price,
                        "type": "sell",
                        "action": "숏 진입",
                    })
                    self.log(f"SELL EXECUTED (숏 진입), Price: {trade_price:.2f}")
                else:
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

        is_aligned = self._is_aligned()
        is_reverse = self._is_reverse_aligned()
        has_gap = self._has_sufficient_gap()  # 간격 조건

        # === 롱 포지션 ===
        if self.params.enable_long:  # type: ignore[attr-defined]
            # 롱 진입: 포지션 없음 + 정배열 시작 + 간격 조건
            if not self.position and is_aligned and not self.was_aligned and has_gap:
                self.log(f"BUY CREATE (롱 진입), Close: {self.dataclose[0]:.2f}")
                self._log_emas()
                self.order = self.buy()

            # 롱 청산: 롱 포지션 + 정배열 붕괴
            elif self.position.size > 0 and not is_aligned:
                self.log(f"SELL CREATE (롱 청산), Close: {self.dataclose[0]:.2f}")
                self._log_emas()
                self.order = self.sell()

        # === 숏 포지션 ===
        if self.params.enable_short:  # type: ignore[attr-defined]
            # 숏 진입: 포지션 없음 + 역배열 시작 + 간격 조건
            if not self.position and is_reverse and not self.was_reverse_aligned and has_gap:
                self.log(f"SELL CREATE (숏 진입), Close: {self.dataclose[0]:.2f}")
                self._log_emas()
                self.order = self.sell()

            # 숏 커버: 숏 포지션 + 역배열 붕괴
            elif self.position.size < 0 and not is_reverse:
                self.log(f"BUY CREATE (숏 커버), Close: {self.dataclose[0]:.2f}")
                self._log_emas()
                self.order = self.buy()

        # 상태 업데이트
        self.was_aligned = is_aligned
        self.was_reverse_aligned = is_reverse
