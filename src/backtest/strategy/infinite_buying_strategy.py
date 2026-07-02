"""무한매수법 전략 (라오어) — docs/무한매수법.md 구현

자금을 N분할(기본 40)하고 T(=매수누적액/회당금액)에 따라 별지점을 계산해
매일 매수(LOC)·매도(쿼터/지정가) 주문을 갱신하는 전략입니다.

핵심 규칙 (docs/무한매수법.md):
- 별지점 = 평단 × (1 + base × (1 - 2T/분할) / 100), base는 종목별 최대 괴리율(TQQQ 15)
- 첫 매수: 전일 종가 × (1+15%) LOC + 여유매수로 회당금액 소진
- 전반전(T < 분할/2): 별지점-0.01에 회당금액 절반, 평단에 나머지 LOC 매수
- 후반전(T >= 분할/2): 별지점-0.01에 회당금액 전체 + 여유매수
- 매도(매일): 잔량 25% 별지점(쿼터매도) + 75% 평단×(1+15%) 지정가매도
- 회차 소진 시: MOC 쿼터매도(종가)만 실행, 매수 금지
- 반복리(기본): 실현 수익 발생 시 회당금액 += 수익/2/분할수
- 전량 청산 시 사이클 종료 → 다음 bar부터 첫 매수 재시작

일봉 백테스트 근사 가정 (매수·매도 모두 종가 기준으로 대칭 모델링):
- 매수(LOC): 전일 수립한 지정가 vs 당일 종가 비교, 종가 <= 지정가면 종가 체결
- 매도(AFTER 지정가): 종가 vs 별지점/목표가 비교, 종가 >= 별지점이면 종가 체결.
  장중 고가 터치가 아니라 종가 기준으로 판정하여 매수 LOC와 동일 시맨틱을 유지한다
  (장중 고가 기반 지정가 체결은 종가가 훨씬 낮게 끝나도 별지점가 매도로 처리되는 낙관 편향이 있어 배제).
- 체결가는 종가 — cheat_on_close로 재현.
- 여유매수: 첫 매수·후반전은 floor(회당금액/종가)로 예산 최대 소진.
"""

import math
from typing import Any

import backtrader as bt

# 매수 수량 상한 계산 시 현금 여유율 (수수료 대비)
_CASH_BUFFER = 0.995


class InfiniteBuyingStrategy(bt.Strategy):
    """무한매수법 전략 (롱 전용, 라오어 방식)

    Params:
        split_count: 분할 수 (기본 40)
        band_base_pct: 별지점 최대 괴리율 %p (TQQQ 15, SOXL 20)
        target_profit_pct: 지정가매도 익절률 %p — 평단 대비 (TQQQ 15, SOXL 20)
        first_buy_loc_pct: 첫 매수 LOC 상한 %p — 전일 종가 대비 (기본 15)
        compound_mode: 회당금액 갱신 방식 — "none"(단리) | "half"(반복리, 기본) | "full"(복리)

    Example:
        >>> cerebro = bt.Cerebro()
        >>> cerebro.addstrategy(InfiniteBuyingStrategy, split_count=40, band_base_pct=15.0)
        >>> cerebro.broker.setcash(100_000_000)
        >>> result = cerebro.run()
    """

    params = (
        ("split_count", 40),
        ("band_base_pct", 15.0),
        ("target_profit_pct", 15.0),
        ("first_buy_loc_pct", 15.0),
        ("compound_mode", "half"),
    )

    def __init__(self) -> None:
        """전략 초기화"""
        self.dataclose = self.datas[0].close

        # 자금 상태 — 회당금액은 반복리/복리 시 수익만큼 갱신됨
        self.per_buy_amount: float = 0.0

        # 보유 미러 — coc 주문은 체결 통지가 다음 bar에 오므로 발주 시점에 선반영하여
        # 당일 계획 수립(T·평단·별지점 계산)에 즉시 사용한다.
        self.hold_qty: int = 0
        self.hold_cost: float = 0.0  # 매수누적액

        # 익일 계획 — buy_plan: (mode, limit, qty). mode "budget"=회당금액 소진, "fixed"=고정 수량
        self.buy_plan: list[tuple[str, float, int]] = []
        # 익일 매도 판정 기준가 (종가 기준). hold_qty>0일 때만 유효.
        self.sell_star: float = 0.0   # 별지점 — 종가 >= 별지점이면 쿼터매도
        self.sell_target: float = 0.0  # 목표가 — 종가 >= 목표가이면 전량 청산
        self.moc_quarter_qty: int = 0  # 소진 시 익일 MOC 쿼터매도 수량 (>0이면 매수 금지)

        # coc 주문 선반영 추적 — 거부/미체결 시 미러 롤백용. ref -> (kind, qty, price_or_avg)
        self.inflight: dict[int, tuple[str, int, float]] = {}

        # 통계/테스트용
        self.cycle_count = 0
        self.buy_executed = False
        self.sell_executed = False
        self.trade_history: list[dict[str, Any]] = []

    def start(self) -> None:
        """전략 시작 — 할당금액·회당금액 확정, cheat_on_close 활성화(LOC/MOC 종가 체결 재현)"""
        self.broker.set_coc(True)
        allocation = self.broker.get_cash()
        self.per_buy_amount = allocation / self.params.split_count  # type: ignore[attr-defined]

    def stop(self) -> None:
        """백테스트 종료 — 마지막 bar에서 발행되어 체결 기회가 없었던 coc 주문의 미러 선반영 롤백

        coc 주문은 발행 다음 broker 사이클에 체결되므로 마지막 bar 발행분은 영원히 미체결이다.
        선반영된 미러를 되돌려 전략 상태를 실제 브로커 포지션과 일치시킨다.
        """
        for kind, qty, price in self.inflight.values():
            if kind == "buy":
                self.hold_qty -= qty
                self.hold_cost -= qty * price
            else:
                self.hold_qty += qty
                self.hold_cost += qty * price
        self.inflight.clear()

    # ------------------------------------------------------------------
    # 파생 값
    # ------------------------------------------------------------------

    def _avg_price(self) -> float:
        """평단 (보유 미러 기준)"""
        return self.hold_cost / self.hold_qty

    def _t_value(self) -> float:
        """T = 매수누적액 / 현재 회당금액"""
        return self.hold_cost / self.per_buy_amount

    def _star_price(self) -> float:
        """별지점 = 평단 × (1 + base × (1 - 2T/분할) / 100)"""
        base = self.params.band_base_pct  # type: ignore[attr-defined]
        split = float(self.params.split_count)  # type: ignore[attr-defined]
        return self._avg_price() * (1 + base * (1 - 2 * self._t_value() / split) / 100)

    # ------------------------------------------------------------------
    # 주문 발행 (coc 시장가 — 종가 체결 + 미러 선반영)
    # ------------------------------------------------------------------

    def _issue_coc_buy(self, qty: int, close: float) -> None:
        """LOC 매수 재현 — 종가 체결 시장가 발주 + 보유 미러 선반영"""
        order = self.buy(size=qty)
        self.inflight[order.ref] = ("buy", qty, close)
        self.hold_qty += qty
        self.hold_cost += qty * close

    def _issue_coc_sell(self, qty: int) -> None:
        """매도 재현 — 종가 체결 시장가 발주 + 보유 미러 선반영 (평단 유지, 누적액 비례 축소)"""
        avg = self._avg_price()
        order = self.sell(size=qty)
        self.inflight[order.ref] = ("sell", qty, avg)
        self.hold_qty -= qty
        self.hold_cost -= qty * avg

    # ------------------------------------------------------------------
    # 회당금액 갱신 (단리/반복리/복리)
    # ------------------------------------------------------------------

    def _apply_compound(self, profit: float) -> None:
        """실현 수익 발생 시 회당금액 갱신 — 반복리: +수익/2/분할, 복리: +수익/분할"""
        if profit <= 0:
            return
        mode = self.params.compound_mode  # type: ignore[attr-defined]
        split = self.params.split_count  # type: ignore[attr-defined]
        if mode == "half":
            self.per_buy_amount += profit / 2 / split
        elif mode == "full":
            self.per_buy_amount += profit / split

    def _finish_cycle(self) -> None:
        """전량 청산 — 사이클 종료 후 상태 초기화 (다음 bar에 첫 매수 계획 수립)"""
        self.cycle_count += 1
        self.hold_qty = 0
        self.hold_cost = 0.0
        self.buy_plan = []
        self.sell_star = 0.0
        self.sell_target = 0.0
        self.moc_quarter_qty = 0
        self.log(f"CYCLE {self.cycle_count} COMPLETE — 전량 청산, 새 사이클 대기")

    # ------------------------------------------------------------------
    # 보일러플레이트
    # ------------------------------------------------------------------

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
            price = order.executed.price
            size = int(round(abs(order.executed.size)))
            inflight = self.inflight.pop(order.ref, None)

            if order.isbuy():
                self.buy_executed = True
                self.trade_history.append({
                    "date": trade_date,
                    "price": price,
                    "type": "buy",
                    "action": "롱 진입",
                })
                self.log(f"BUY EXECUTED {size}주, Price: {price:.2f} (T={self._t_value():.2f})")
            else:
                # 매도는 모두 coc 시장가 — 미러는 발주 시 선반영됨, 여기선 수익만 계산.
                self.sell_executed = True
                avg = inflight[2] if inflight is not None else price
                profit = (price - avg) * size
                self._apply_compound(profit)
                self.trade_history.append({
                    "date": trade_date,
                    "price": price,
                    "type": "sell",
                    "action": "롱 청산",
                })
                self.log(f"SELL EXECUTED {size}주, Price: {price:.2f}, 실현손익: {profit:,.0f}")
                if self.hold_qty <= 0:
                    self._finish_cycle()

        elif order.status in [order.Margin, order.Rejected, order.Canceled]:
            # coc 주문이 거부되면 선반영한 미러를 롤백
            inflight = self.inflight.pop(order.ref, None)
            if inflight is not None:
                kind, qty, price = inflight
                if kind == "buy":
                    self.hold_qty -= qty
                    self.hold_cost -= qty * price
                else:
                    self.hold_qty += qty
                    self.hold_cost += qty * price
                self.log(f"{kind.upper()} 거부/취소 — 미러 롤백 ({qty}주)")

    # ------------------------------------------------------------------
    # 메인 루프
    # ------------------------------------------------------------------

    def next(self) -> None:
        """매 bar: 종가 기준으로 매도/매수를 판정(우선순위: 소진 MOC → 매도 → 매수)한 뒤 익일 계획 갱신"""
        close = float(self.dataclose[0])

        # ① 회차 소진 — MOC 쿼터매도만, 매수 금지
        if self.moc_quarter_qty > 0:
            qty = min(self.moc_quarter_qty, self.hold_qty)
            if qty > 0:
                self._issue_coc_sell(qty)
                self.log(f"MOC QUARTER SELL {qty}주 @ {close:.2f} (소진 모드)")

        # ② 매도 (종가 >= 별지점). 목표가 이상이면 전량 청산, 아니면 쿼터매도.
        elif self.hold_qty > 0 and close >= self.sell_star:
            if close >= self.sell_target:
                self._issue_coc_sell(self.hold_qty)
            else:
                quarter = self.hold_qty // 4
                if quarter > 0:
                    self._issue_coc_sell(quarter)

        # ③ 매수 (종가 <= 지정가). 별지점 지정가는 항상 별지점보다 낮으므로 ②와 상호배타.
        elif self.buy_plan:
            qty = 0
            for mode, limit, fixed_qty in self.buy_plan:
                if close <= limit:
                    qty += math.floor(self.per_buy_amount / close) if mode == "budget" else fixed_qty
            cap = math.floor(self.broker.get_cash() * _CASH_BUFFER / close)
            qty = min(qty, cap)
            if qty > 0:
                self._issue_coc_buy(qty, close)

        self._plan_next_bar(close)

    def _plan_next_bar(self, prev_close: float) -> None:
        """익일 매수 계획(buy_plan)과 매도 판정 기준가(sell_star/sell_target)를 현재 미러 상태로 수립"""
        self.buy_plan = []
        self.moc_quarter_qty = 0

        # 첫 매수 — 전일 종가 × (1 + 15%) LOC + 여유매수(예산 소진)
        if self.hold_qty <= 0:
            self.sell_star = 0.0
            self.sell_target = 0.0
            limit = prev_close * (1 + self.params.first_buy_loc_pct / 100)  # type: ignore[attr-defined]
            self.buy_plan = [("budget", limit, 0)]
            return

        avg = self._avg_price()
        t = self._t_value()
        split = float(self.params.split_count)  # type: ignore[attr-defined]
        self.sell_star = self._star_price()
        self.sell_target = avg * (1 + self.params.target_profit_pct / 100)  # type: ignore[attr-defined]

        # 소진 판정: T가 분할수에 도달했거나 현금이 반 회분에도 못 미치면 1회차 매수 불가
        if t >= split or self.broker.get_cash() < self.per_buy_amount * 0.5:
            self.moc_quarter_qty = self.hold_qty // 4
            return

        # 매수 계획 (매도는 next에서 종가 기준 평가)
        if t < split / 2:
            # 전반전 — 별지점-0.01에 회당금액 절반, 평단에 나머지
            p1 = self.sell_star - 0.01
            q1 = math.floor(self.per_buy_amount / 2 / p1)
            q2 = max(math.floor(self.per_buy_amount / avg) - q1, 0)
            self.buy_plan = [("fixed", p1, q1), ("fixed", avg, q2)]
        else:
            # 후반전 — 별지점-0.01에 회당금액 전체 + 여유매수(예산 소진)
            self.buy_plan = [("budget", self.sell_star - 0.01, 0)]
