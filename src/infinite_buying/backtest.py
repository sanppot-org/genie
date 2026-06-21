"""무한매수법 v1 백테스트 하니스 (순수 — KIS·DB 의존 0).

과거 일봉(수정주가)으로 일별 루프를 돌린다: build_daily_plan(계획) → 체결 시뮬레이션
→ position_math 상태 갱신 → 사이클 종료/재시작. 체결 규칙·현금모델은 계획서 Global Constraints 참조.
"""

from dataclasses import dataclass
from datetime import date

from src.infinite_buying.domain.order_plan import OrderIntent, build_daily_plan
from src.infinite_buying.domain.per_round_amount import Compounding, update_per_round_amount
from src.infinite_buying.domain.position_math import (
    PositionState,
    apply_buy,
    apply_sell,
    is_cycle_complete,
    next_cycle_seed,
)


@dataclass(frozen=True)
class DailyBar:
    """백테스트 일봉 1행 (수정주가 기준)."""

    date: date
    high: float
    close: float


@dataclass(frozen=True)
class BacktestConfig:
    """종목별 무한매수법 파라미터."""

    division: int
    base_gap: float
    sell_limit_pct: float
    allocation: float
    compounding: Compounding = Compounding.HALF


@dataclass(frozen=True)
class BacktestResult:
    """백테스트 결과 지표."""

    total_return: float
    max_drawdown: float
    num_cycles: int
    num_days: int
    num_buys: int
    num_sells: int
    final_equity: float


@dataclass
class _SimState:
    """루프 진행용 가변 상태 (순수 모듈 내부)."""

    position: PositionState
    per_round_amount: float
    cash: float
    cycle_no: int
    num_cycles: int = 0
    num_buys: int = 0
    num_sells: int = 0


def run_backtest(bars: list[DailyBar], config: BacktestConfig) -> BacktestResult:
    """일봉 리스트로 무한매수법 v1을 시뮬레이션해 지표를 반환한다."""
    per_round0 = config.allocation / config.division if config.division else 0.0
    sim = _SimState(
        position=PositionState(holding_qty=0, cumulative_buy=0.0),
        per_round_amount=per_round0,
        cash=config.allocation,
        cycle_no=1,
    )

    if not bars:
        return BacktestResult(0.0, 0.0, 0, 0, 0, 0, config.allocation)

    peak = config.allocation
    max_dd = 0.0
    # day 0: 계획 없음(전일종가 부재), equity만 기록
    equity = sim.cash + sim.position.holding_qty * bars[0].close
    peak, max_dd = _update_dd(peak, max_dd, equity)

    for i in range(1, len(bars)):
        bar = bars[i]
        prev_close = bars[i - 1].close
        plan = build_daily_plan(
            state=sim.position,
            per_round_amount=sim.per_round_amount,
            prev_close=prev_close,
            division=config.division,
            base_gap=config.base_gap,
            sell_limit_pct=config.sell_limit_pct,
            allocation=config.allocation,
        )
        had_position = sim.position.holding_qty > 0
        _apply_day(sim, plan, bar, config)
        if had_position and is_cycle_complete(sim.position):
            sim.num_cycles += 1
            sim.position, sim.cycle_no = next_cycle_seed(sim.cycle_no)
        equity = sim.cash + sim.position.holding_qty * bar.close
        peak, max_dd = _update_dd(peak, max_dd, equity)

    final_equity = sim.cash + sim.position.holding_qty * bars[-1].close
    total_return = final_equity / config.allocation - 1 if config.allocation else 0.0
    return BacktestResult(
        total_return=total_return,
        max_drawdown=max_dd,
        num_cycles=sim.num_cycles,
        num_days=len(bars),
        num_buys=sim.num_buys,
        num_sells=sim.num_sells,
        final_equity=final_equity,
    )


def _apply_day(sim: _SimState, plan: list[OrderIntent], bar: DailyBar, config: BacktestConfig) -> None:
    """하루치 계획을 체결 시뮬레이션해 상태에 반영 (매수 → 쿼터매도 → 지정가매도 순)."""
    buys = [i for i in plan if i.side == "buy"]
    quarters = [i for i in plan if i.order_kind == "quarter_sell"]
    limits = [i for i in plan if i.order_kind == "limit_sell"]

    for intent in buys:  # LOC 매수: 종가 <= 목표가 → 종가 체결
        if bar.close <= intent.target_price:
            sim.position = apply_buy(sim.position, bar.close, intent.qty)
            sim.cash -= bar.close * intent.qty
            sim.num_buys += 1

    for intent in quarters:
        fill_price = _quarter_fill_price(intent, bar)
        if fill_price is not None:
            _apply_sell(sim, fill_price, intent.qty, config)

    for intent in limits:  # 지정가매도: 고가 >= 목표가 → 목표가 체결
        if bar.high >= intent.target_price:
            _apply_sell(sim, intent.target_price, intent.qty, config)


def _quarter_fill_price(intent: OrderIntent, bar: DailyBar) -> float | None:
    """쿼터매도 체결가 (MOC: 항상 종가, LOC: 종가>=목표가일 때 종가). 미체결이면 None."""
    if intent.order_division == "MOC":
        return bar.close
    if bar.close >= intent.target_price:  # LOC 매도
        return bar.close
    return None


def _apply_sell(sim: _SimState, fill_price: float, qty: int, config: BacktestConfig) -> None:
    """매도 체결 1건 반영: 상태·현금·회당금액(반복리) 갱신."""
    sim.position, realized = apply_sell(sim.position, fill_price, qty)
    sim.cash += fill_price * qty
    sim.per_round_amount = update_per_round_amount(
        sim.per_round_amount, realized, config.division, config.compounding
    )
    sim.num_sells += 1


def _update_dd(peak: float, max_dd: float, equity: float) -> tuple[float, float]:
    """자산 곡선 갱신 → (새 peak, 새 max_drawdown)."""
    new_peak = max(peak, equity)
    dd = (new_peak - equity) / new_peak if new_peak > 0 else 0.0
    return new_peak, max(max_dd, dd)
