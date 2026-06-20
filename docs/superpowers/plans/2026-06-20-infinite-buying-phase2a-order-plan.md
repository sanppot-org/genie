# 무한매수법 Phase 2a — 주문계획 도메인(order_plan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 포지션 상태·config·전일종가를 받아 그날 KIS에 걸 주문 intent 목록을 산출하는 순수 도메인 함수 `build_daily_plan`을 구현한다(KIS·DB 의존 0, 단위테스트).

**Architecture:** Phase 1 도메인 원시 함수(separation_point, calc_t/phase_of, PositionState)를 조합하는 순수 함수. v1 규칙(스펙 §10): 여유매수 없음, 정규장 주문만(매수 LOC, 지정가매도 LIMIT, 회차소진 시 쿼터매도 MOC). KIS 발주·체결은 Phase 2b 어댑터, 오케스트레이션은 Phase 2c.

**Tech Stack:** Python 3.12, dataclasses, pytest, ruff, mypy, uv.

**참조:** 스펙 `docs/superpowers/specs/2026-06-20-infinite-buying-design.md` (§4 데이터흐름, §10 v1 범위), 원전 `docs/무한매수법.md` §4~§5.

## Global Constraints

- 도메인 모듈(`src/infinite_buying/domain/**`)은 KIS·DB·SQLAlchemy import 금지 — 순수 함수만(다른 domain 모듈 import는 허용).
- v1 주문 규칙: 매수=LOC(별지점매수·평단매수·첫매수), 지정가매도=LIMIT, 회차소진 쿼터매도=MOC, 평상시 쿼터매도=LOC. 여유매수 단 없음.
- 수량 산식(원전 §4~§5 그대로):
  - 첫매수: `floor(회당금액 / (전일종가 × 1.15))`
  - 전반전 별지점매수: `floor((회당금액/2) / 별지점목표가)`; 평단매수: `floor(회당금액 / 평단) − 별지점매수수량`
  - 후반전 별지점매수: `floor(회당금액 / 별지점목표가)`
  - 쿼터매도: `floor(잔량/4)`; 지정가매도: `잔량 − 쿼터매도수량`
- 별지점매수 목표가 = `별지점 − 0.01`(매도와 겹침 방지). 쿼터매도 목표가 = `별지점`(오프셋 없음). 지정가매도 목표가 = `평단 × (1 + sell_limit_pct/100)`.
- 매수 가능 판정(affordable): `매수누적액 + 회당금액 <= 할당금액`. 불가 시 회차소진 경로(매도만, 쿼터=MOC).
- `qty <= 0`인 intent는 결과에서 제외.
- 문자열 값은 모델 컬럼과 일치: side `buy`/`sell`; order_kind `first_buy`/`separation_buy`/`avg_buy`/`quarter_sell`/`limit_sell`; order_division `LOC`/`MOC`/`LIMIT`.
- Python 3.12, ruff line-length 180, 룰 E,F,W,I,N,UP,ANN,B,A,C4. 타입 어노테이션 필수.

---

## File Structure

- `src/infinite_buying/domain/order_plan.py` (생성) — `OrderIntent` dataclass + `build_daily_plan` + 내부 헬퍼.
- `tests/infinite_buying/domain/test_order_plan.py` (생성) — 시나리오별 단위테스트.

---

## Task 1: `order_plan.py` — 하루치 주문계획

**Files:**
- Create: `src/infinite_buying/domain/order_plan.py`
- Test: `tests/infinite_buying/domain/test_order_plan.py`

**Interfaces:**
- Consumes (Phase 1 도메인): `PositionState`(position_math), `calc_t`/`phase_of`/`Phase`(progress), `separation_point`(separation_point).
- Produces:
  - `OrderIntent` (frozen dataclass): `side: str`, `order_kind: str`, `order_division: str`, `target_price: float`, `qty: int`
  - `build_daily_plan(state: PositionState, per_round_amount: float, prev_close: float, division: int, base_gap: float, sell_limit_pct: float, allocation: float) -> list[OrderIntent]`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/domain/test_order_plan.py`:

```python
"""하루치 주문계획 산출 (무한매수법 v1) — docs/무한매수법.md §4~§5, 스펙 §10."""

from math import floor

import pytest

from src.infinite_buying.domain.order_plan import OrderIntent, build_daily_plan
from src.infinite_buying.domain.position_math import PositionState
from src.infinite_buying.domain.progress import calc_t
from src.infinite_buying.domain.separation_point import separation_point


def _by_kind(plan: list[OrderIntent]) -> dict[str, OrderIntent]:
    return {i.order_kind: i for i in plan}


def test_cycle_start_emits_single_loc_first_buy() -> None:
    # 보유 0 → 첫매수만(LOC), 목표가=전일종가×1.15, 수량=floor(회당금액/목표가)
    plan = build_daily_plan(
        state=PositionState(holding_qty=0, cumulative_buy=0.0),
        per_round_amount=250.0, prev_close=50.0,
        division=40, base_gap=15.0, sell_limit_pct=15.0, allocation=10000.0,
    )
    assert len(plan) == 1
    fb = plan[0]
    assert fb.side == "buy" and fb.order_kind == "first_buy" and fb.order_division == "LOC"
    assert fb.target_price == pytest.approx(57.5)
    assert fb.qty == floor(250.0 / 57.5)  # = 4


def test_first_half_emits_separation_avg_buys_plus_sells() -> None:
    state = PositionState(holding_qty=16, cumulative_buy=740.0)  # 평단 46.25
    plan = build_daily_plan(
        state=state, per_round_amount=250.0, prev_close=999.0,
        division=40, base_gap=15.0, sell_limit_pct=15.0, allocation=10000.0,
    )
    kinds = _by_kind(plan)
    assert set(kinds) == {"separation_buy", "avg_buy", "quarter_sell", "limit_sell"}

    t = calc_t(740.0, 250.0)  # 2.96 < 20 → 전반전
    sep = separation_point(46.25, t, 40, 15.0)
    sep_target = sep - 0.01

    sb = kinds["separation_buy"]
    assert sb.side == "buy" and sb.order_division == "LOC"
    assert sb.target_price == pytest.approx(sep_target)
    assert sb.qty == floor((250.0 / 2) / sep_target)  # = 2

    ab = kinds["avg_buy"]
    assert ab.order_division == "LOC" and ab.target_price == pytest.approx(46.25)
    assert ab.qty == floor(250.0 / 46.25) - floor((250.0 / 2) / sep_target)  # 5 - 2 = 3

    qs = kinds["quarter_sell"]
    assert qs.side == "sell" and qs.order_division == "LOC"
    assert qs.target_price == pytest.approx(sep)  # 쿼터매도는 별지점(오프셋 없음)
    assert qs.qty == floor(16 / 4)  # = 4

    ls = kinds["limit_sell"]
    assert ls.order_division == "LIMIT"
    assert ls.target_price == pytest.approx(46.25 * 1.15)
    assert ls.qty == 16 - floor(16 / 4)  # = 12


def test_second_half_emits_full_separation_buy_only_plus_sells() -> None:
    state = PositionState(holding_qty=200, cumulative_buy=5000.0)  # 평단 25, T=20 → 후반전
    plan = build_daily_plan(
        state=state, per_round_amount=250.0, prev_close=999.0,
        division=40, base_gap=15.0, sell_limit_pct=15.0, allocation=10000.0,
    )
    kinds = _by_kind(plan)
    assert "avg_buy" not in kinds  # 후반전은 평단매수 없음
    assert set(kinds) == {"separation_buy", "quarter_sell", "limit_sell"}

    t = calc_t(5000.0, 250.0)  # 20.0 → 후반전
    sep = separation_point(25.0, t, 40, 15.0)
    sb = kinds["separation_buy"]
    assert sb.qty == floor(250.0 / (sep - 0.01))  # 회당금액 전액
    assert kinds["quarter_sell"].qty == floor(200 / 4)  # 50


def test_budget_exhausted_emits_moc_quarter_sell_no_buys() -> None:
    # 매수누적액+회당금액 > 할당금액 → 회차 소진: 매도만, 쿼터매도는 MOC
    state = PositionState(holding_qty=40, cumulative_buy=9900.0)  # 평단 247.5
    plan = build_daily_plan(
        state=state, per_round_amount=250.0, prev_close=999.0,
        division=40, base_gap=15.0, sell_limit_pct=15.0, allocation=10000.0,
    )
    kinds = _by_kind(plan)
    assert not any(i.side == "buy" for i in plan)  # 매수 없음
    assert kinds["quarter_sell"].order_division == "MOC"
    assert kinds["quarter_sell"].qty == floor(40 / 4)  # 10
    assert kinds["limit_sell"].order_division == "LIMIT"
    assert kinds["limit_sell"].qty == 40 - floor(40 / 4)  # 30


def test_zero_qty_intents_are_dropped() -> None:
    # 잔량 3 → 쿼터매도 floor(3/4)=0 → 제외, 지정가매도는 전량(3)
    state = PositionState(holding_qty=3, cumulative_buy=150.0)  # 평단 50
    plan = build_daily_plan(
        state=state, per_round_amount=250.0, prev_close=999.0,
        division=40, base_gap=15.0, sell_limit_pct=15.0, allocation=10000.0,
    )
    kinds = _by_kind(plan)
    assert "quarter_sell" not in kinds          # 0주 → 제외
    assert kinds["limit_sell"].qty == 3         # 전량
    assert all(i.qty > 0 for i in plan)         # 모든 intent qty>0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/domain/test_order_plan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying.domain.order_plan'`

- [ ] **Step 3: Write the implementation**

Create `src/infinite_buying/domain/order_plan.py`:

```python
"""하루치 주문계획 산출 (무한매수법 v1).

포지션 상태·config·전일종가 → 그날 KIS에 걸 주문 intent 목록.
v1 범위(스펙 §10): 여유매수 없음, 정규장 주문만.
- 보유 0(사이클 시작): 첫 매수(LOC).
- 매수 가능(매수누적액+회당금액 <= 할당금액): 매수(전반=별지점½+평단, 후반=별지점 전액)[LOC]
  + 매도(쿼터매도 별지점[LOC] + 지정가매도[LIMIT]).
- 회차 소진(매수 불가): 매도만 — 쿼터매도(MOC) + 지정가매도(LIMIT).
KIS 발주는 Phase 2b 어댑터, 상태 갱신은 Phase 2c 대조잡 책임. 원전: docs/무한매수법.md §4~§5.
"""

from dataclasses import dataclass
from math import floor

from src.infinite_buying.domain.position_math import PositionState
from src.infinite_buying.domain.progress import Phase, calc_t, phase_of
from src.infinite_buying.domain.separation_point import separation_point

FIRST_BUY_PRICE_RATIO = 1.15  # 첫 매수 LOC 목표가 = 전일종가 × 1.15 (진입 보장 위해 널널하게)
SEPARATION_OFFSET = 0.01      # 별지점매수 목표가는 매도와 겹치지 않게 -0.01


@dataclass(frozen=True)
class OrderIntent:
    """그날 걸 주문 1건 (도메인 표현; KIS 발주는 어댑터 책임)."""

    side: str            # buy / sell
    order_kind: str      # first_buy / separation_buy / avg_buy / quarter_sell / limit_sell
    order_division: str  # LOC / MOC / LIMIT
    target_price: float
    qty: int


def build_daily_plan(
    state: PositionState,
    per_round_amount: float,
    prev_close: float,
    division: int,
    base_gap: float,
    sell_limit_pct: float,
    allocation: float,
) -> list[OrderIntent]:
    """그날의 주문 intent 목록을 산출한다 (qty<=0 intent는 제외)."""
    if state.holding_qty == 0:
        target = prev_close * FIRST_BUY_PRICE_RATIO
        qty = floor(per_round_amount / target) if target > 0 else 0
        return _nonempty([OrderIntent("buy", "first_buy", "LOC", target, qty)])

    t = calc_t(state.cumulative_buy, per_round_amount)
    sep = separation_point(state.avg_price, t, division, base_gap)
    affordable = state.cumulative_buy + per_round_amount <= allocation

    intents: list[OrderIntent] = []
    if affordable:
        intents.extend(_buy_intents(state, per_round_amount, sep, phase_of(t, division)))
        intents.extend(_sell_intents(state, sep, sell_limit_pct, "LOC"))
    else:
        intents.extend(_sell_intents(state, sep, sell_limit_pct, "MOC"))
    return _nonempty(intents)


def _buy_intents(
    state: PositionState, per_round_amount: float, sep: float, phase: Phase
) -> list[OrderIntent]:
    """전반전: 별지점매수(½)+평단매수(나머지). 후반전: 별지점매수(전액). 모두 LOC."""
    sep_target = sep - SEPARATION_OFFSET
    if phase is Phase.FIRST_HALF:
        sep_qty = floor((per_round_amount / 2) / sep_target) if sep_target > 0 else 0
        avg_qty = floor(per_round_amount / state.avg_price) - sep_qty if state.avg_price > 0 else 0
        return [
            OrderIntent("buy", "separation_buy", "LOC", sep_target, sep_qty),
            OrderIntent("buy", "avg_buy", "LOC", state.avg_price, avg_qty),
        ]
    sep_qty = floor(per_round_amount / sep_target) if sep_target > 0 else 0
    return [OrderIntent("buy", "separation_buy", "LOC", sep_target, sep_qty)]


def _sell_intents(
    state: PositionState, sep: float, sell_limit_pct: float, quarter_division: str
) -> list[OrderIntent]:
    """쿼터매도(잔량25%, 별지점, 평상시 LOC/회차소진 MOC) + 지정가매도(나머지, 평단+%)."""
    quarter_qty = floor(state.holding_qty / 4)
    limit_qty = state.holding_qty - quarter_qty
    limit_target = state.avg_price * (1 + sell_limit_pct / 100)
    return [
        OrderIntent("sell", "quarter_sell", quarter_division, sep, quarter_qty),
        OrderIntent("sell", "limit_sell", "LIMIT", limit_target, limit_qty),
    ]


def _nonempty(intents: list[OrderIntent]) -> list[OrderIntent]:
    """qty>0인 intent만 남긴다."""
    return [i for i in intents if i.qty > 0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/domain/test_order_plan.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint + type check**

Run: `uv run ruff check src/infinite_buying/ tests/infinite_buying/ && uv run mypy src/infinite_buying/`
Expected: clean.

- [ ] **Step 6: Confirm domain purity (no DB/KIS import)**

Run: `uv run python -c "import ast; n=ast.parse(open('src/infinite_buying/domain/order_plan.py').read()); bad=[m for x in ast.walk(n) if isinstance(x,(ast.Import,ast.ImportFrom)) for m in ([x.module] if isinstance(x,ast.ImportFrom) else [a.name for a in x.names]) if m and ('database' in m or 'hantu' in m or 'sqlalchemy' in m)]; print('IMPURE:',bad) if bad else print('pure ok')"`
Expected: `pure ok`

- [ ] **Step 7: Commit**

```bash
git add src/infinite_buying/domain/order_plan.py tests/infinite_buying/domain/test_order_plan.py
git commit -m "feat(infinite-buying): add order_plan domain (daily order intents, v1)"
```

---

## Self-Review Notes

- **Spec coverage (Phase 2a 범위):** 원전 §4 첫매수/전반전(별지점½+평단)/후반전(별지점 전액), §5 쿼터매도(별지점)+지정가매도(평단+%), 회차소진(쿼터 MOC) → 모두 `build_daily_plan` 분기에 매핑. v1 결정(여유매수 없음, 정규장 주문, affordable 판정) 반영.
- **Type consistency:** `OrderIntent`의 side/order_kind/order_division 문자열이 Phase 1 `InfiniteBuyingOrder` 모델 컬럼 코멘트(buy/sell, first_buy/separation_buy/avg_buy/quarter_sell/limit_sell, LOC/MOC/LIMIT)와 일치 → Phase 2c에서 intent→InfiniteBuyingOrder 매핑 시 변환 불필요. `PositionState`/`calc_t`/`phase_of`/`Phase`/`separation_point`는 Phase 1 구현 시그니처 그대로 소비.
- **No placeholders:** 모든 분기에 완전 코드/테스트 포함. 여유매수·AFTER지정가는 stub 없이 v1 범위에서 제외(스펙 §10 명시).
- **경계:** intent는 "무엇을 걸지"만 표현. 실제 KIS 발주(Phase 2b)·원장 기록/체결대조(Phase 2c)는 범위 밖.
- **알려진 한계(Phase 2b/2c에서 처리):** 첫매수 회당금액 기준(현재 per_round_amount 사용 = 신규 사이클서 allocation/division과 동일), LOC 종가체결 예산 미소진(여유매수 후속), 부분체결 반영은 대조잡.
