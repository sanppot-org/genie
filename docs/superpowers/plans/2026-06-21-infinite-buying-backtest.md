# 무한매수법 백테스트 하니스 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 과거 일봉(수정주가)으로 무한매수법 v1을 시뮬레이션해 총수익률·MDD·사이클수를 산출하는 순수 백테스트 하니스와, 로컬 DB 캔들을 읽어 실행하는 러너 스크립트를 만든다.

**Architecture:** Phase 1·2a 도메인 함수(build_daily_plan, position_math, update_per_round_amount)를 조합하는 순수 모듈 `src/infinite_buying/backtest.py`. 일별 루프로 계획 산출 → 체결 시뮬 → 상태 갱신을 반복한다. KIS·DB 의존 0. 러너(`scripts/`)는 `stock_daily_candle_repository`로 adj 캔들을 읽어 하니스에 전달.

**Tech Stack:** Python 3.12, dataclasses, pytest, ruff, mypy, uv.

**참조:** 백테스트 설계(이 세션), 스펙 §10(v1 규칙), 원전 `docs/무한매수법.md` §4~§5.

## Global Constraints

- `src/infinite_buying/backtest.py`는 **순수 모듈** — `src.infinite_buying.domain.*` + dataclasses/표준라이브러리만 import. KIS·DB·SQLAlchemy import 금지.
- 가격은 **adj(수정주가)** 기준. 러너가 `adj_high`/`adj_close`(없으면 `high`/`close` 폴백)를 `DailyBar`로 변환.
- 체결 규칙(설계 확정):
  - LOC 매수(first_buy/separation_buy/avg_buy): `bar.close <= target_price` → **종가(bar.close)**로 체결.
  - LOC 쿼터매도: `bar.close >= target_price` → 종가 체결. MOC 쿼터매도: 항상 종가 체결.
  - 지정가매도(limit_sell): `bar.high >= target_price` → **목표가(target_price)**로 체결.
- 같은 날 체결 적용 순서: **매수 → 쿼터매도 → 지정가매도** (결정성). 매도 실현수익으로 `update_per_round_amount(반복리=HALF)` 갱신.
- 사이클: 보유 0 도달 시 사이클 종료(카운트+1) → `next_cycle_seed`로 새 사이클(회당금액 이월).
- 현금/자산: `cash`는 `allocation`에서 시작 → 매수 체결 시 `-= 체결가×수량`, 매도 시 `+= 체결가×수량`. `equity = cash + 보유수량×종가`. 총수익률 = `최종 equity / allocation − 1`. MDD = equity 곡선 최대 낙폭.
- 계획은 i=1부터(전일종가 = `bars[i-1].close` 필요). i=0은 equity만 기록(=allocation).
- Python 3.12, ruff line-length 180, 룰 E,F,W,I,N,UP,ANN,B,A,C4(테스트 ANN001/201/202·N802 무시). mypy 통과.

---

## File Structure

- `src/infinite_buying/backtest.py` (생성) — `DailyBar`, `BacktestConfig`, `BacktestResult`, `run_backtest` + 내부 체결 헬퍼.
- `tests/infinite_buying/test_backtest.py` (생성) — 합성 캔들로 시나리오 검증.
- `scripts/backtest_infinite_buying.py` (생성) — 로컬 DB adj 캔들 로드 → run_backtest → 결과 출력.

---

## Task 1: 순수 백테스트 하니스 (`backtest.py`)

**Files:**
- Create: `src/infinite_buying/backtest.py`
- Test: `tests/infinite_buying/test_backtest.py`

**Interfaces:**
- Consumes: `build_daily_plan`(order_plan), `PositionState`/`apply_buy`/`apply_sell`/`is_cycle_complete`/`next_cycle_seed`(position_math), `update_per_round_amount`/`Compounding`(per_round_amount).
- Produces:
  - `DailyBar` (frozen dataclass): `date: date`, `high: float`, `close: float`
  - `BacktestConfig` (frozen dataclass): `division: int`, `base_gap: float`, `sell_limit_pct: float`, `allocation: float`, `compounding: Compounding = Compounding.HALF`
  - `BacktestResult` (frozen dataclass): `total_return: float`, `max_drawdown: float`, `num_cycles: int`, `num_days: int`, `num_buys: int`, `num_sells: int`, `final_equity: float`
  - `run_backtest(bars: list[DailyBar], config: BacktestConfig) -> BacktestResult`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/test_backtest.py`:

```python
"""무한매수법 백테스트 하니스 (순수) — 체결 시뮬레이션 + 사이클 검증."""

from datetime import date, timedelta

import pytest

from src.infinite_buying.backtest import BacktestConfig, DailyBar, run_backtest


def _bars(closes: list[float], highs: list[float] | None = None) -> list[DailyBar]:
    """종가 리스트로 일봉 생성 (high 미지정 시 close와 동일)."""
    base = date(2024, 1, 1)
    hs = highs if highs is not None else closes
    return [DailyBar(date=base + timedelta(days=i), high=hs[i], close=closes[i]) for i in range(len(closes))]


def _cfg(allocation: float = 10000.0) -> BacktestConfig:
    return BacktestConfig(division=40, base_gap=15.0, sell_limit_pct=15.0, allocation=allocation)


def test_no_trades_when_price_never_triggers_first_buy() -> None:
    # 첫매수 목표가 = 전일종가×1.15. 종가가 계속 상승하면(>목표가) LOC 매수 미체결 → 보유 0 유지.
    bars = _bars([100.0, 130.0, 170.0])  # day1: prev=100→target=115, close130>115 미체결; day2: prev130→target149.5, close170>149.5 미체결
    result = run_backtest(bars, _cfg())
    assert result.num_buys == 0
    assert result.num_cycles == 0
    assert result.final_equity == pytest.approx(10000.0)  # 현금 전액 보존
    assert result.total_return == pytest.approx(0.0)


def test_first_buy_fills_when_close_below_target() -> None:
    # day1: prev=100 → target=115, close=50<=115 → 첫매수 체결. 회당금액=allocation/division=250, qty=floor(250/50)=5.
    bars = _bars([100.0, 50.0])
    result = run_backtest(bars, _cfg())
    assert result.num_buys == 1
    # 보유 5주 @50 → equity = (10000-250) + 5*50 = 9750+250 = 10000 (체결 직후 동일가)
    assert result.final_equity == pytest.approx(10000.0)
    assert result.num_cycles == 0  # 아직 청산 전


def test_full_cycle_buy_then_profitable_limit_sell() -> None:
    # day1 첫매수(close=50, qty5), day2 지정가매도(평단50×1.15=57.5, high=60>=57.5 체결).
    # 첫매수 후 보유5 평단50. day2 plan: 전반전 → 별지점매수/평단매수 + 쿼터매도/지정가매도.
    # day2 close=60 (>별지점, >평단 → 매수 미체결), high=60 → limit_sell(57.5) 체결, quarter_sell(별지점)도 close>=별지점이면 체결.
    bars = _bars([100.0, 50.0, 60.0], highs=[100.0, 50.0, 60.0])
    result = run_backtest(bars, _cfg())
    assert result.num_buys >= 1
    assert result.num_sells >= 1
    # 수익 실현으로 최종 자산 > 초기 (매도가 일부라도 이익)
    assert result.final_equity > 10000.0
    assert result.num_days == 3


def test_metrics_have_expected_shape() -> None:
    bars = _bars([100.0, 50.0, 45.0, 70.0], highs=[100.0, 55.0, 48.0, 75.0])
    result = run_backtest(bars, _cfg())
    assert result.num_days == 4
    assert 0.0 <= result.max_drawdown <= 1.0
    assert result.num_buys >= 0 and result.num_sells >= 0


def test_empty_or_single_bar_returns_flat() -> None:
    assert run_backtest([], _cfg()).total_return == pytest.approx(0.0)
    one = run_backtest(_bars([100.0]), _cfg())
    assert one.num_days == 1 and one.num_buys == 0 and one.final_equity == pytest.approx(10000.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/test_backtest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying.backtest'`

- [ ] **Step 3: Write the implementation**

Create `src/infinite_buying/backtest.py`:

```python
"""무한매수법 v1 백테스트 하니스 (순수 — KIS·DB 의존 0).

과거 일봉(수정주가)으로 일별 루프를 돌린다: build_daily_plan(계획) → 체결 시뮬레이션
→ position_math 상태 갱신 → 사이클 종료/재시작. 체결 규칙·현금모델은 계획서 Global Constraints 참조.
"""

from dataclasses import dataclass, field
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
        _apply_day(sim, plan, bar, config)
        if is_cycle_complete(sim.position):
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
```

> 참고: `field`는 사용하지 않으면 import에서 제거할 것(ruff F401). 위 코드엔 `field` 미사용이므로 `from dataclasses import dataclass`만 남긴다.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/test_backtest.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint + type check + purity**

Run: `uv run ruff check src/infinite_buying/ tests/infinite_buying/ && uv run mypy src/infinite_buying/`
Expected: clean.

Run: `uv run python -c "import ast; n=ast.parse(open('src/infinite_buying/backtest.py').read()); bad=[m for x in ast.walk(n) if isinstance(x,(ast.Import,ast.ImportFrom)) for m in ([x.module] if isinstance(x,ast.ImportFrom) else [a.name for a in x.names]) if m and ('database' in m or 'hantu' in m or 'sqlalchemy' in m)]; print('IMPURE:',bad) if bad else print('pure ok')"`
Expected: `pure ok`

- [ ] **Step 6: Commit**

```bash
git add src/infinite_buying/backtest.py tests/infinite_buying/test_backtest.py
git commit -m "feat(infinite-buying): add pure backtest harness (v1, adj prices)"
```

---

## Task 2: 러너 스크립트 (`scripts/backtest_infinite_buying.py`)

**Files:**
- Create: `scripts/backtest_infinite_buying.py`

**Interfaces:**
- Consumes: `Database`/`container`(DI), `TickerRepository`, `StockDailyCandleRepository.find_by_ticker`, `backtest.run_backtest`/`DailyBar`/`BacktestConfig`.

- [ ] **Step 1: Write the script**

Create `scripts/backtest_infinite_buying.py`:

```python
"""무한매수법 백테스트 러너 (로컬 DB adj 일봉 사용).

사용:
    ENV_PROFILE=local uv run python scripts/backtest_infinite_buying.py --ticker TQQQ --base-gap 15 \
        --start 20200101 --end 20241231 --allocation 10000 --division 40

선행: 해당 티커 일봉이 stock_daily_candles에 백필돼 있어야 한다(register_us_tickers.py + backfill_us_daily_candles.py).
adj_close/adj_high가 있으면 그것을, 없으면 close/high를 사용한다.
"""

import argparse
from datetime import datetime
import logging

from src.container import ApplicationContainer
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.infinite_buying.backtest import BacktestConfig, DailyBar, run_backtest

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest infinite-buying strategy on local adj daily candles.")
    parser.add_argument("--ticker", required=True, help="종목 코드 (예: TQQQ)")
    parser.add_argument("--base-gap", type=float, required=True, help="종목별 최대 괴리율 (TQQQ=15, SOXL=20)")
    parser.add_argument("--sell-limit-pct", type=float, default=None, help="지정가매도 %% (기본: base-gap과 동일)")
    parser.add_argument("--division", type=int, default=40, help="분할수 (기본 40)")
    parser.add_argument("--allocation", type=float, default=10000.0, help="할당금액 (기본 10000)")
    parser.add_argument("--start", default=None, help="시작일 YYYYMMDD")
    parser.add_argument("--end", default=None, help="종료일 YYYYMMDD")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from_date = datetime.strptime(args.start, "%Y%m%d").date() if args.start else None
    to_date = datetime.strptime(args.end, "%Y%m%d").date() if args.end else None
    sell_limit_pct = args.sell_limit_pct if args.sell_limit_pct is not None else args.base_gap

    database = ApplicationContainer().database()
    with database.session_scope() as session:
        ticker = TickerRepository(session).find_by_ticker(args.ticker)
        if ticker is None or ticker.id is None:
            raise SystemExit(f"티커 미등록: {args.ticker} (register_us_tickers.py로 먼저 등록)")
        rows = StockDailyCandleRepository(session).find_by_ticker(ticker.id, from_date, to_date)

    bars = [
        DailyBar(
            date=r.date,
            high=r.adj_high if r.adj_high is not None else r.high,
            close=r.adj_close if r.adj_close is not None else r.close,
        )
        for r in rows
    ]
    if not bars:
        raise SystemExit(f"일봉 데이터 없음: {args.ticker} (backfill_us_daily_candles.py로 백필)")

    config = BacktestConfig(
        division=args.division,
        base_gap=args.base_gap,
        sell_limit_pct=sell_limit_pct,
        allocation=args.allocation,
    )
    result = run_backtest(bars, config)

    logger.info("=== 무한매수법 백테스트: %s (%s ~ %s, %d거래일) ===", args.ticker, bars[0].date, bars[-1].date, result.num_days)
    logger.info("총수익률: %.2f%%", result.total_return * 100)
    logger.info("MDD: %.2f%%", result.max_drawdown * 100)
    logger.info("사이클 수: %d", result.num_cycles)
    logger.info("매수 체결: %d건 / 매도 체결: %d건", result.num_buys, result.num_sells)
    logger.info("최종 자산: %.2f (할당 %.2f)", result.final_equity, args.allocation)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the script imports/parses**

Run: `uv run python -c "import ast; ast.parse(open('scripts/backtest_infinite_buying.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Lint**

Run: `uv run ruff check scripts/backtest_infinite_buying.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add scripts/backtest_infinite_buying.py
git commit -m "feat(infinite-buying): add backtest runner script (local adj candles)"
```

---

## Self-Review Notes

- **Spec coverage:** 순수 하니스(Task 1) — 일별 build_daily_plan→체결 시뮬→position_math 갱신→사이클 재시작, 현금/equity·MDD·사이클 지표. 러너(Task 2) — adj 캔들 로드→실행→출력. 설계서의 체결 규칙·현금모델·매수우선 적용순서 반영.
- **Type consistency:** `OrderIntent.side`/`order_kind`/`order_division`(buy/sell, quarter_sell/limit_sell, LOC/MOC/LIMIT) 분기가 Phase 2a 산출값과 일치. `DailyBar`/`BacktestConfig`/`BacktestResult`는 러너가 동일 시그니처로 소비.
- **순수성:** backtest.py는 domain만 import(테스트에서 ast로 검증). 러너만 DB 접근.
- **No placeholders:** 모든 코드/테스트 완전. `field` 미사용 import 제거 주의 명시.
- **알려진 한계:** v1 충실도(여유매수 없음), adj 근사(실제 달러 주문가와 미세 차이), 동일일 매수·매도 동시체결은 매수우선 가정. 배당 재투자·수수료·세금 미반영(단순 가격 시뮬). 결과는 전략 형태 비교용이며 실거래 수익 보장 아님.
- **데이터 의존:** 러너는 백필된 캔들 필요. TQQQ/SOXL 백필은 구현 후 별도 실행(스크립트 기존재: register_us_tickers.py, backfill_us_daily_candles.py).
