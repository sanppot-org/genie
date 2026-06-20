# 무한매수법 Phase 1 — 도메인 코어 + 영속화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 무한매수법의 *돈이 걸린 순수 계산*(별지점·T·회당금액 갱신·체결 반영 평단 재계산)을 KIS·DB 의존 0으로 단위테스트와 함께 구현하고, 자체 원장 3개 테이블(설정/포지션/주문)과 영속화 리포지토리를 만든다.

**Architecture:** 헥사고날 — `src/infinite_buying/domain/`은 입력값(평단·T·회당금액·체결 등)을 받아 숫자만 반환하는 순수 함수 모음(외부 의존 0). 원장 모델은 코드베이스 관례대로 중앙 `src/database/models.py`에 정의(alembic autogenerate·`Base.metadata`가 스캔). 리포지토리는 bounded context를 묶기 위해 `src/infinite_buying/repository.py`에 모듈-로컬로 둔다. Phase 1은 KIS 어댑터·서비스 오케스트레이션·스케줄·order_plan 합성을 포함하지 않는다(Phase 2).

**Tech Stack:** Python 3.12, SQLAlchemy 2.x (`Mapped`/`mapped_column`), Postgres, Alembic, pytest, ruff, mypy, uv.

**참조 스펙:** `docs/superpowers/specs/2026-06-20-infinite-buying-design.md`

## Global Constraints

- Python 3.12, ruff line-length 180, 룰 `E,F,W,I,N,UP,ANN,B,A,C4`. production 코드는 타입 어노테이션 필수.
- 도메인 모듈(`src/infinite_buying/domain/**`)은 **KIS·DB·SQLAlchemy를 import 금지** (순수 함수만).
- enum 값은 DB에 **문자열(`.value`)로 저장** (SQLAlchemy `Enum` 타입 미사용 — us-stock 선례와 동일).
- 금액·가격은 `Float` (코드베이스 OHLC 관례와 일치).
- `alembic upgrade`는 **대상 호스트 확인 + 사용자 승인 후에만** 실행 (CLAUDE.md 규칙; `.env.dev`가 prod를 가리킬 수 있음).
- 매 태스크 커밋 전 변경 파일에 대해 ruff/mypy 통과.

---

## File Structure

- `src/infinite_buying/__init__.py` (생성) — 패키지 마커.
- `src/infinite_buying/domain/__init__.py` (생성) — 패키지 마커.
- `src/infinite_buying/domain/separation_point.py` (생성) — 별지점 계산.
- `src/infinite_buying/domain/progress.py` (생성) — T 계산 + `Phase` 판정.
- `src/infinite_buying/domain/per_round_amount.py` (생성) — 회당금액 갱신 + `Compounding`.
- `src/infinite_buying/domain/position_math.py` (생성) — `PositionState` + 체결 반영(매수/매도) + 사이클 종료 판정.
- `src/database/models.py` (수정, 파일 끝에 추가) — `InfiniteBuyingConfig` / `InfiniteBuyingPosition` / `InfiniteBuyingOrder` 모델.
- `alembic/versions/019_add_infinite_buying_tables.py` (생성) — 3개 테이블 마이그레이션.
- `src/infinite_buying/repository.py` (생성) — `InfiniteBuyingConfigRepository` / `InfiniteBuyingPositionRepository`.
- 테스트: `tests/infinite_buying/domain/test_separation_point.py`, `test_progress.py`, `test_per_round_amount.py`, `test_position_math.py`, `tests/infinite_buying/test_repository.py`.

---

## Task 1: 별지점 계산 (`domain/separation_point.py`)

**Files:**
- Create: `src/infinite_buying/__init__.py`
- Create: `src/infinite_buying/domain/__init__.py`
- Create: `src/infinite_buying/domain/separation_point.py`
- Test: `tests/infinite_buying/domain/test_separation_point.py`

**Interfaces:**
- Produces: `separation_point(avg_price: float, t: float, division: int, base_gap: float) -> float`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/domain/test_separation_point.py`:

```python
"""별지점 공식 검산 (docs/무한매수법.md §3)."""

import pytest

from src.infinite_buying.domain.separation_point import separation_point


def test_t_zero_returns_avg_times_full_base() -> None:
    # T=0 → 평단 * (1 + base%)
    assert separation_point(avg_price=100.0, t=0.0, division=40, base_gap=15.0) == pytest.approx(115.0)


def test_t_half_division_returns_avg() -> None:
    # T = 분할/2 → 정확히 평단
    assert separation_point(avg_price=100.0, t=20.0, division=40, base_gap=15.0) == pytest.approx(100.0)


def test_tqqq_40div_midpoint() -> None:
    # TQQQ base=15, 40분할, T=10 → 15*(1-20/40)=7.5 → 평단*1.075
    assert separation_point(avg_price=100.0, t=10.0, division=40, base_gap=15.0) == pytest.approx(107.5)


def test_soxl_base_20_t_zero() -> None:
    # SOXL base=20, T=0 → 평단*1.20
    assert separation_point(avg_price=50.0, t=0.0, division=40, base_gap=20.0) == pytest.approx(60.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/domain/test_separation_point.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying'`

- [ ] **Step 3: Create package markers + implementation**

Create `src/infinite_buying/__init__.py`:

```python
"""무한매수법(라오어 매매법) 자동매매 모듈."""
```

Create `src/infinite_buying/domain/__init__.py`:

```python
"""무한매수법 순수 도메인 코어 (KIS·DB 의존 0)."""
```

Create `src/infinite_buying/domain/separation_point.py`:

```python
"""별지점 계산 (매수/매도를 가르는 기준점).

별지점 = 평단 * (1 + base * (1 - 2T/분할) / 100)
  - base_gap: 종목별 최대 괴리율(%포인트, 15는 15%를 의미하며 0.15가 아님)
  - T=0 → 평단*(1+base%), T=분할/2 → 평단
원전: docs/무한매수법.md §3.
"""


def separation_point(avg_price: float, t: float, division: int, base_gap: float) -> float:
    """평단·T·분할수·base 괴리율로 별지점을 계산한다.

    Args:
        avg_price: 평단가.
        t: 현재 T값 (매수누적액 / 회당금액).
        division: 분할수 (예: 40).
        base_gap: 종목별 최대 괴리율(%포인트). TQQQ=15, SOXL=20.

    Returns:
        별지점 가격.
    """
    return avg_price * (1 + base_gap * (1 - 2 * t / division) / 100)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/domain/test_separation_point.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/__init__.py src/infinite_buying/domain/__init__.py src/infinite_buying/domain/separation_point.py tests/infinite_buying/domain/test_separation_point.py
git commit -m "feat(infinite-buying): add separation_point pure formula"
```

---

## Task 2: T 계산 + 전반전/후반전 판정 (`domain/progress.py`)

**Files:**
- Create: `src/infinite_buying/domain/progress.py`
- Test: `tests/infinite_buying/domain/test_progress.py`

**Interfaces:**
- Produces:
  - `Phase(StrEnum)` with members `FIRST_HALF = "first_half"`, `SECOND_HALF = "second_half"`
  - `calc_t(cumulative_buy: float, per_round_amount: float) -> float`
  - `phase_of(t: float, division: int) -> Phase`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/domain/test_progress.py`:

```python
"""T 계산 및 전반전/후반전 판정 (docs/무한매수법.md §3~§4)."""

import pytest

from src.infinite_buying.domain.progress import Phase, calc_t, phase_of


def test_calc_t_divides_cumulative_by_per_round() -> None:
    assert calc_t(cumulative_buy=2000.0, per_round_amount=250.0) == pytest.approx(8.0)


def test_calc_t_zero_when_per_round_non_positive() -> None:
    assert calc_t(cumulative_buy=2000.0, per_round_amount=0.0) == 0.0


def test_phase_first_half_below_half_division() -> None:
    assert phase_of(t=8.0, division=40) is Phase.FIRST_HALF


def test_phase_second_half_at_and_above_half_division() -> None:
    # T == 분할/2 부터 후반전 (T>=분할/2)
    assert phase_of(t=20.0, division=40) is Phase.SECOND_HALF
    assert phase_of(t=25.0, division=40) is Phase.SECOND_HALF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/domain/test_progress.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying.domain.progress'`

- [ ] **Step 3: Write the implementation**

Create `src/infinite_buying/domain/progress.py`:

```python
"""진행도(T)와 전반전/후반전 판정.

T = 매수누적액 / 회당금액(현재). 회차가 분할/2 미만이면 전반전, 이상이면 후반전.
원전: docs/무한매수법.md §3~§4.
"""

from enum import StrEnum


class Phase(StrEnum):
    """전반전/후반전 구분."""

    FIRST_HALF = "first_half"    # T < 분할/2
    SECOND_HALF = "second_half"  # T >= 분할/2


def calc_t(cumulative_buy: float, per_round_amount: float) -> float:
    """T = 매수누적액 / 회당금액. 회당금액이 0 이하면 0.0."""
    if per_round_amount <= 0:
        return 0.0
    return cumulative_buy / per_round_amount


def phase_of(t: float, division: int) -> Phase:
    """T와 분할수로 전반전/후반전 판정 (T >= 분할/2 → 후반전)."""
    return Phase.SECOND_HALF if t >= division / 2 else Phase.FIRST_HALF
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/domain/test_progress.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/domain/progress.py tests/infinite_buying/domain/test_progress.py
git commit -m "feat(infinite-buying): add T calc + first/second half phase"
```

---

## Task 3: 회당금액 갱신 (`domain/per_round_amount.py`)

**Files:**
- Create: `src/infinite_buying/domain/per_round_amount.py`
- Test: `tests/infinite_buying/domain/test_per_round_amount.py`

**Interfaces:**
- Produces:
  - `Compounding(StrEnum)` with members `SIMPLE = "simple"`, `HALF = "half"`, `FULL = "full"`
  - `update_per_round_amount(current: float, realized_profit: float, division: int, mode: Compounding) -> float`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/domain/test_per_round_amount.py`:

```python
"""회당금액 갱신 (단리/반복리/복리) — docs/무한매수법.md §4."""

import pytest

from src.infinite_buying.domain.per_round_amount import Compounding, update_per_round_amount


def test_simple_keeps_amount_fixed() -> None:
    assert update_per_round_amount(250.0, realized_profit=80.0, division=40, mode=Compounding.SIMPLE) == 250.0


def test_half_adds_profit_over_two_division() -> None:
    # 반복리(기본): 회당금액 + 수익/2/분할수 → 250 + 80/2/40 = 251
    assert update_per_round_amount(250.0, realized_profit=80.0, division=40, mode=Compounding.HALF) == pytest.approx(251.0)


def test_full_adds_profit_over_division() -> None:
    # 복리: 회당금액 + 수익/분할수 → 250 + 80/40 = 252
    assert update_per_round_amount(250.0, realized_profit=80.0, division=40, mode=Compounding.FULL) == pytest.approx(252.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/domain/test_per_round_amount.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying.domain.per_round_amount'`

- [ ] **Step 3: Write the implementation**

Create `src/infinite_buying/domain/per_round_amount.py`:

```python
"""회당금액(1회매수액) 갱신 — 수익 발생 시 복리 방식에 따라 증가.

- 단리(SIMPLE): 고정.
- 반복리(HALF, 기본): 회당금액 + 수익/2/분할수.
- 복리(FULL): 회당금액 + 수익/분할수.
예) 250불, 수익 80불, 40분할 → 반복리 251불, 복리 252불.
원전: docs/무한매수법.md §4.
"""

from enum import StrEnum


class Compounding(StrEnum):
    """회당금액 갱신 방식."""

    SIMPLE = "simple"  # 단리: 고정
    HALF = "half"      # 반복리(기본)
    FULL = "full"      # 복리


def update_per_round_amount(
    current: float,
    realized_profit: float,
    division: int,
    mode: Compounding,
) -> float:
    """실현 수익을 반영해 회당금액을 갱신한다.

    Args:
        current: 현재 회당금액.
        realized_profit: 이번에 실현된 수익(매도 차익).
        division: 분할수.
        mode: 단리/반복리/복리.

    Returns:
        갱신된 회당금액.
    """
    if mode is Compounding.SIMPLE:
        return current
    if mode is Compounding.HALF:
        return current + realized_profit / 2 / division
    return current + realized_profit / division
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/domain/test_per_round_amount.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/domain/per_round_amount.py tests/infinite_buying/domain/test_per_round_amount.py
git commit -m "feat(infinite-buying): add per-round-amount update (simple/half/full)"
```

---

## Task 4: 체결 반영 평단 재계산 (`domain/position_math.py`)

**Files:**
- Create: `src/infinite_buying/domain/position_math.py`
- Test: `tests/infinite_buying/domain/test_position_math.py`

**Interfaces:**
- Consumes: 없음 (순수).
- Produces:
  - `PositionState` (frozen dataclass): `holding_qty: int`, `cumulative_buy: float`, property `avg_price: float`
  - `apply_buy(state: PositionState, fill_price: float, fill_qty: int) -> PositionState`
  - `apply_sell(state: PositionState, fill_price: float, fill_qty: int) -> tuple[PositionState, float]` — (새 상태, 실현수익)
  - `is_cycle_complete(state: PositionState) -> bool`

불변식: `avg_price == cumulative_buy / holding_qty` (보유 0이면 0.0). 매도는 평단을 바꾸지 않고 매수누적액을 비례 감소시킨다 → T가 비례 하락(쿼터매도 시 ≈0.75배). 이 값들이 Task 3 `update_per_round_amount(realized_profit=...)`의 입력이 된다.

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/domain/test_position_math.py`:

```python
"""체결 반영 평단·보유·매수누적액 재계산 (docs/무한매수법.md §4~§5)."""

import pytest

from src.infinite_buying.domain.position_math import (
    PositionState,
    apply_buy,
    apply_sell,
    is_cycle_complete,
)


def test_empty_state_avg_price_is_zero() -> None:
    s = PositionState(holding_qty=0, cumulative_buy=0.0)
    assert s.avg_price == 0.0


def test_apply_buy_accumulates_and_averages() -> None:
    s = PositionState(holding_qty=0, cumulative_buy=0.0)
    s = apply_buy(s, fill_price=50.0, fill_qty=10)
    assert s.holding_qty == 10
    assert s.cumulative_buy == pytest.approx(500.0)
    assert s.avg_price == pytest.approx(50.0)
    # 물타기: 6주 @ $40
    s = apply_buy(s, fill_price=40.0, fill_qty=6)
    assert s.holding_qty == 16
    assert s.cumulative_buy == pytest.approx(740.0)
    assert s.avg_price == pytest.approx(46.25)


def test_apply_sell_keeps_avg_reduces_cumulative_and_returns_profit() -> None:
    s = PositionState(holding_qty=16, cumulative_buy=740.0)  # 평단 46.25
    new_state, realized = apply_sell(s, fill_price=55.0, fill_qty=4)  # 쿼터매도 floor(16/4)=4
    assert new_state.holding_qty == 12
    # 매수누적액은 평단*매도수량(46.25*4=185)만큼 감소 → 555
    assert new_state.cumulative_buy == pytest.approx(555.0)
    # 평단 불변
    assert new_state.avg_price == pytest.approx(46.25)
    # 실현수익 = (55 - 46.25) * 4 = 35
    assert realized == pytest.approx(35.0)


def test_quarter_sell_drops_cumulative_to_about_three_quarters() -> None:
    # T ≈ 0.75배 하락 검증 (매수누적액 비례 감소)
    s = PositionState(holding_qty=16, cumulative_buy=740.0)
    new_state, _ = apply_sell(s, fill_price=55.0, fill_qty=4)
    assert new_state.cumulative_buy / s.cumulative_buy == pytest.approx(0.75)


def test_full_liquidation_completes_cycle() -> None:
    s = PositionState(holding_qty=12, cumulative_buy=555.0)
    new_state, _ = apply_sell(s, fill_price=60.0, fill_qty=12)
    assert new_state.holding_qty == 0
    assert new_state.cumulative_buy == pytest.approx(0.0)
    assert is_cycle_complete(new_state) is True


def test_cycle_not_complete_while_holding() -> None:
    assert is_cycle_complete(PositionState(holding_qty=5, cumulative_buy=200.0)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/domain/test_position_math.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying.domain.position_math'`

- [ ] **Step 3: Write the implementation**

Create `src/infinite_buying/domain/position_math.py`:

```python
"""체결 1건을 반영해 포지션 상태(평단·보유수량·매수누적액)를 재계산한다.

불변식: 평단 = 매수누적액 / 보유수량. 매도는 평단을 바꾸지 않고
매수누적액을 평단×매도수량만큼 비례 감소시킨다(→ T 비례 하락, 쿼터매도 시 ≈0.75배).
매도 차익(realized profit)은 회당금액 갱신(per_round_amount)의 입력이 된다.
원전: docs/무한매수법.md §4~§5.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionState:
    """무한매수법 사이클의 핵심 상태 (평단은 파생)."""

    holding_qty: int
    cumulative_buy: float

    @property
    def avg_price(self) -> float:
        """평단 = 매수누적액 / 보유수량 (보유 0이면 0.0)."""
        if self.holding_qty <= 0:
            return 0.0
        return self.cumulative_buy / self.holding_qty


def apply_buy(state: PositionState, fill_price: float, fill_qty: int) -> PositionState:
    """매수 체결 반영: 보유수량·매수누적액 증가(평단은 파생 재계산)."""
    return PositionState(
        holding_qty=state.holding_qty + fill_qty,
        cumulative_buy=state.cumulative_buy + fill_price * fill_qty,
    )


def apply_sell(state: PositionState, fill_price: float, fill_qty: int) -> tuple[PositionState, float]:
    """매도 체결 반영: 보유수량·매수누적액 비례 감소. 반환 (새 상태, 실현수익).

    매수누적액은 평단×매도수량(원가)만큼 줄어 평단이 유지된다.
    실현수익 = (체결가 - 평단) × 매도수량.
    """
    avg = state.avg_price
    new_qty = state.holding_qty - fill_qty
    new_cumulative = state.cumulative_buy - avg * fill_qty
    realized = (fill_price - avg) * fill_qty
    return PositionState(holding_qty=new_qty, cumulative_buy=max(new_cumulative, 0.0)), realized


def is_cycle_complete(state: PositionState) -> bool:
    """보유수량이 0이면 사이클 종료(전량 청산)."""
    return state.holding_qty == 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/domain/test_position_math.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/domain/position_math.py tests/infinite_buying/domain/test_position_math.py
git commit -m "feat(infinite-buying): add fill-applied position math + cycle completion"
```

---

## Task 5: 원장 DB 모델 3개 + 마이그레이션

**Files:**
- Modify: `src/database/models.py` (파일 끝에 모델 3개 추가)
- Create: `alembic/versions/019_add_infinite_buying_tables.py`
- Test: `tests/infinite_buying/test_repository.py` (Task 6에서 작성 — 본 태스크는 인메모리 `create_all`로 스키마만 검증)

**Interfaces:**
- Produces (SQLAlchemy 모델, `src.database.models`에서 import):
  - `InfiniteBuyingConfig`: `id`, `ticker_id:int`, `division:int`, `base_gap:float`, `allocation:float`, `compounding:str`, `sell_limit_pct:float`, `active:bool`
  - `InfiniteBuyingPosition`: `id`, `ticker_id:int`, `cycle_no:int`, `holding_qty:int`, `cumulative_buy:float`, `per_round_amount:float`, `phase:str`, `status:str`, `realized_pnl:float`
  - `InfiniteBuyingOrder`: `id`, `position_id:int`, `kis_order_no:str|None`, `side:str`, `order_kind:str`, `order_division:str`, `target_price:float`, `qty:int`, `status:str`, `filled_qty:int`, `filled_price:float|None`, `trade_date:date|None`

- [ ] **Step 1: Write the failing schema test**

Create `tests/infinite_buying/test_repository.py` (스키마 스모크 테스트 먼저, 리포지토리 본문은 Task 6에서 확장):

```python
"""무한매수법 원장 모델/리포지토리 테스트 (인메모리 SQLite)."""

from sqlalchemy.orm import Session

from src.database.models import (
    InfiniteBuyingConfig,
    InfiniteBuyingOrder,
    InfiniteBuyingPosition,
)


def test_models_persist_via_create_all(session: Session) -> None:
    """Base.metadata.create_all로 3개 테이블이 생성되고 행이 저장된다."""
    cfg = InfiniteBuyingConfig(
        ticker_id=1, division=40, base_gap=15.0, allocation=10000.0,
        compounding="half", sell_limit_pct=15.0, active=True,
    )
    pos = InfiniteBuyingPosition(
        ticker_id=1, cycle_no=1, holding_qty=0, cumulative_buy=0.0,
        per_round_amount=250.0, phase="first_half", status="active", realized_pnl=0.0,
    )
    session.add_all([cfg, pos])
    session.flush()
    order = InfiniteBuyingOrder(
        position_id=pos.id, kis_order_no=None, side="buy", order_kind="first_buy",
        order_division="LOC", target_price=57.5, qty=4, status="pending",
        filled_qty=0, filled_price=None, trade_date=None,
    )
    session.add(order)
    session.flush()

    assert cfg.id is not None
    assert pos.id is not None
    assert order.id is not None and order.position_id == pos.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/test_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'InfiniteBuyingConfig' from 'src.database.models'`

- [ ] **Step 3: Add the models**

Append to the end of `src/database/models.py`:

```python
class InfiniteBuyingConfig(Base, TimestampMixin):
    """무한매수법 종목별 파라미터 (사이클 무관 설정, 종목당 1행)."""

    __tablename__ = "infinite_buying_config"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ticker_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    division: Mapped[int] = mapped_column(Integer, nullable=False, default=40, comment="분할수")
    base_gap: Mapped[float] = mapped_column(Float, nullable=False, comment="종목별 최대 괴리율(%포인트): TQQQ=15, SOXL=20")
    allocation: Mapped[float] = mapped_column(Float, nullable=False, comment="할당금액")
    compounding: Mapped[str] = mapped_column(String(8), nullable=False, default="half", comment="회당금액 갱신: simple/half/full")
    sell_limit_pct: Mapped[float] = mapped_column(Float, nullable=False, comment="지정가매도 %: TQQQ=15, SOXL=20")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true(), default=True)

    def __repr__(self) -> str:
        return f"<InfiniteBuyingConfig(ticker_id={self.ticker_id}, division={self.division}, compounding={self.compounding})>"


class InfiniteBuyingPosition(Base, TimestampMixin):
    """무한매수법 사이클 상태 (진실의 근원, 사이클당 1행)."""

    __tablename__ = "infinite_buying_position"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ticker_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="사이클 번호 (1부터)")
    holding_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="보유수량")
    cumulative_buy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="매수누적액")
    per_round_amount: Mapped[float] = mapped_column(Float, nullable=False, comment="현재 회당금액")
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default="first_half", comment="first_half/second_half (T 파생 캐시)")
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="active", comment="active/closed")
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="사이클 누적 실현손익")

    __table_args__ = (
        Index("ix_ib_position_ticker_cycle", "ticker_id", "cycle_no", unique=True),
    )

    def __repr__(self) -> str:
        return f"<InfiniteBuyingPosition(ticker_id={self.ticker_id}, cycle_no={self.cycle_no}, holding_qty={self.holding_qty}, status={self.status})>"


class InfiniteBuyingOrder(Base, TimestampMixin):
    """무한매수법 발주 원장 (발주잡이 PENDING 기록, 대조잡이 체결 갱신)."""

    __tablename__ = "infinite_buying_order"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    position_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    kis_order_no: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="KIS 주문번호")
    side: Mapped[str] = mapped_column(String(4), nullable=False, comment="buy/sell")
    order_kind: Mapped[str] = mapped_column(String(24), nullable=False, comment="first_buy/separation_buy/avg_buy/extra_buy/quarter_sell/limit_sell")
    order_division: Mapped[str] = mapped_column(String(8), nullable=False, comment="LOC/MOC/LIMIT")
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="pending", comment="pending/filled/unfilled/canceled")
    filled_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filled_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="체결일")

    def __repr__(self) -> str:
        return f"<InfiniteBuyingOrder(position_id={self.position_id}, kind={self.order_kind}, status={self.status})>"
```

> 참고: `BigInteger, Boolean, Date, Float, Identity, Index, Integer, String, true`와 `Mapped, mapped_column`은 이미 `models.py` 상단에서 import되어 있다(파일 1-26행 확인). 추가 import 불필요.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/test_repository.py -v`
Expected: PASS (1 test — 테스트는 `Base.metadata.create_all`로 스키마 생성, 마이그레이션 불필요)

- [ ] **Step 5: Create the Alembic migration**

Create `alembic/versions/019_add_infinite_buying_tables.py`:

```python
"""Add infinite buying ledger tables

Revision ID: 019_infinite_buying
Revises: 018_ticker_exchange
Create Date: 2026-06-20

무한매수법 자체 원장 3개 테이블: 설정/포지션/주문.
신규 테이블 생성이라 기존 테이블 잠금 없음.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_infinite_buying"
down_revision: str | Sequence[str] | None = "018_ticker_exchange"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create infinite_buying_config / _position / _order tables."""
    op.create_table(
        "infinite_buying_config",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("division", sa.Integer(), nullable=False),
        sa.Column("base_gap", sa.Float(), nullable=False),
        sa.Column("allocation", sa.Float(), nullable=False),
        sa.Column("compounding", sa.String(length=8), nullable=False),
        sa.Column("sell_limit_pct", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker_id"),
    )
    op.create_index("ix_infinite_buying_config_ticker_id", "infinite_buying_config", ["ticker_id"])

    op.create_table(
        "infinite_buying_position",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False),
        sa.Column("holding_qty", sa.Integer(), nullable=False),
        sa.Column("cumulative_buy", sa.Float(), nullable=False),
        sa.Column("per_round_amount", sa.Float(), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_infinite_buying_position_ticker_id", "infinite_buying_position", ["ticker_id"])
    op.create_index("ix_ib_position_ticker_cycle", "infinite_buying_position", ["ticker_id", "cycle_no"], unique=True)

    op.create_table(
        "infinite_buying_order",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("position_id", sa.BigInteger(), nullable=False),
        sa.Column("kis_order_no", sa.String(length=32), nullable=True),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("order_kind", sa.String(length=24), nullable=False),
        sa.Column("order_division", sa.String(length=8), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("filled_qty", sa.Integer(), nullable=False),
        sa.Column("filled_price", sa.Float(), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_infinite_buying_order_position_id", "infinite_buying_order", ["position_id"])


def downgrade() -> None:
    """Drop infinite buying tables."""
    op.drop_index("ix_infinite_buying_order_position_id", table_name="infinite_buying_order")
    op.drop_table("infinite_buying_order")
    op.drop_index("ix_ib_position_ticker_cycle", table_name="infinite_buying_position")
    op.drop_index("ix_infinite_buying_position_ticker_id", table_name="infinite_buying_position")
    op.drop_table("infinite_buying_position")
    op.drop_index("ix_infinite_buying_config_ticker_id", table_name="infinite_buying_config")
    op.drop_table("infinite_buying_config")
```

- [ ] **Step 6: Verify the migration is the new head (no DB write yet)**

Run: `uv run alembic heads`
Expected: `019_infinite_buying (head)`

- [ ] **Step 7: Confirm DB host BEFORE applying (사용자 승인 필수)**

> ⚠️ CLAUDE.md 규칙: `alembic upgrade` 전 대상 호스트를 확인하고 사용자 승인을 받는다.

Run: `uv run python -c "from src.config import DatabaseConfig; print(DatabaseConfig().database_url)"`
Expected: 로컬 docker(`localhost`/`127.0.0.1`)인지 확인. **대상이 로컬임을 사용자에게 명시하고 승인받은 뒤** 다음 단계로. prod면 중단.

- [ ] **Step 8: Apply the migration (승인 후)**

Run: `ENV_PROFILE=local uv run alembic upgrade head`
Expected: `Running upgrade 018_ticker_exchange -> 019_infinite_buying`

- [ ] **Step 9: Commit**

```bash
git add src/database/models.py alembic/versions/019_add_infinite_buying_tables.py tests/infinite_buying/test_repository.py
git commit -m "feat(infinite-buying): add ledger tables (config/position/order) + migration"
```

---

## Task 6: 원장 리포지토리 (`repository.py`)

**Files:**
- Create: `src/infinite_buying/repository.py`
- Modify: `tests/infinite_buying/test_repository.py` (CRUD 테스트 추가)

**Interfaces:**
- Consumes: `InfiniteBuyingConfig`, `InfiniteBuyingPosition` (Task 5), `BaseRepository` (`src/database/base_repository.py`).
- Produces:
  - `InfiniteBuyingConfigRepository(session)`: `save(cfg) -> InfiniteBuyingConfig`, `find_by_ticker_id(ticker_id: int) -> InfiniteBuyingConfig | None`, `find_active() -> list[InfiniteBuyingConfig]`
  - `InfiniteBuyingPositionRepository(session)`: `save(pos) -> InfiniteBuyingPosition`, `find_active_by_ticker(ticker_id: int) -> InfiniteBuyingPosition | None`

- [ ] **Step 1: Add the failing CRUD test**

Append to `tests/infinite_buying/test_repository.py`:

```python
from src.infinite_buying.repository import (
    InfiniteBuyingConfigRepository,
    InfiniteBuyingPositionRepository,
)


def test_config_repo_save_and_find(session: Session) -> None:
    repo = InfiniteBuyingConfigRepository(session)
    repo.save(InfiniteBuyingConfig(
        ticker_id=10, division=40, base_gap=20.0, allocation=10000.0,
        compounding="half", sell_limit_pct=20.0, active=True,
    ))
    found = repo.find_by_ticker_id(10)
    assert found is not None
    assert found.base_gap == 20.0
    assert repo.find_by_ticker_id(999) is None


def test_config_repo_find_active_excludes_inactive(session: Session) -> None:
    repo = InfiniteBuyingConfigRepository(session)
    repo.save(InfiniteBuyingConfig(ticker_id=1, division=40, base_gap=15.0, allocation=10000.0, compounding="half", sell_limit_pct=15.0, active=True))
    repo.save(InfiniteBuyingConfig(ticker_id=2, division=40, base_gap=20.0, allocation=10000.0, compounding="half", sell_limit_pct=20.0, active=False))
    active = repo.find_active()
    assert {c.ticker_id for c in active} == {1}


def test_position_repo_find_active_by_ticker(session: Session) -> None:
    repo = InfiniteBuyingPositionRepository(session)
    repo.save(InfiniteBuyingPosition(ticker_id=5, cycle_no=1, holding_qty=0, cumulative_buy=0.0, per_round_amount=250.0, phase="first_half", status="closed", realized_pnl=10.0))
    repo.save(InfiniteBuyingPosition(ticker_id=5, cycle_no=2, holding_qty=4, cumulative_buy=200.0, per_round_amount=250.0, phase="first_half", status="active", realized_pnl=0.0))
    active = repo.find_active_by_ticker(5)
    assert active is not None
    assert active.cycle_no == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying.repository'`

- [ ] **Step 3: Write the implementation**

Create `src/infinite_buying/repository.py`:

```python
"""무한매수법 원장 리포지토리 (설정/포지션).

`BaseRepository.save()`는 unique 제약 기준 upsert(flush only). 커밋은 호출자 책임.
주문(InfiniteBuyingOrder) 영속화는 발주/대조 서비스가 도입되는 Phase 2에서 추가한다.
"""

from src.database.base_repository import BaseRepository
from src.database.models import InfiniteBuyingConfig, InfiniteBuyingPosition


class InfiniteBuyingConfigRepository(BaseRepository[InfiniteBuyingConfig, int]):
    """종목별 무한매수법 설정 리포지토리 (종목당 1행)."""

    def _get_model_class(self) -> type[InfiniteBuyingConfig]:
        return InfiniteBuyingConfig

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id",)

    def find_by_ticker_id(self, ticker_id: int) -> InfiniteBuyingConfig | None:
        """종목 설정 조회."""
        return (
            self.session.query(InfiniteBuyingConfig)
            .filter(InfiniteBuyingConfig.ticker_id == ticker_id)
            .first()
        )

    def find_active(self) -> list[InfiniteBuyingConfig]:
        """활성 설정 전체 조회 (발주잡 대상 종목)."""
        return (
            self.session.query(InfiniteBuyingConfig)
            .filter(InfiniteBuyingConfig.active.is_(True))
            .order_by(InfiniteBuyingConfig.ticker_id)
            .all()
        )


class InfiniteBuyingPositionRepository(BaseRepository[InfiniteBuyingPosition, int]):
    """무한매수법 사이클 상태 리포지토리 ((ticker_id, cycle_no) 유니크)."""

    def _get_model_class(self) -> type[InfiniteBuyingPosition]:
        return InfiniteBuyingPosition

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "cycle_no")

    def find_active_by_ticker(self, ticker_id: int) -> InfiniteBuyingPosition | None:
        """진행 중(status=active)인 사이클 조회 (종목당 최대 1개)."""
        return (
            self.session.query(InfiniteBuyingPosition)
            .filter(
                InfiniteBuyingPosition.ticker_id == ticker_id,
                InfiniteBuyingPosition.status == "active",
            )
            .order_by(InfiniteBuyingPosition.cycle_no.desc())
            .first()
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/test_repository.py -v`
Expected: PASS (4 tests — 스키마 1 + CRUD 3)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/repository.py tests/infinite_buying/test_repository.py
git commit -m "feat(infinite-buying): add config/position ledger repositories"
```

---

## Task 7: 전체 검증 + 스펙 갱신

**Files:**
- Modify: `docs/superpowers/specs/2026-06-20-infinite-buying-design.md` (Phase 1 완료 표기)

- [ ] **Step 1: Full lint/type/test sweep**

Run: `uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest tests/infinite_buying/ -q`
Expected: all pass (도메인 17 + 리포지토리 4 = 21 tests).

- [ ] **Step 2: Confirm domain purity (no KIS/DB imports)**

Run: `uv run python -c "import ast,glob; bad=[f for f in glob.glob('src/infinite_buying/domain/*.py') for n in [ast.parse(open(f).read())] if any('database' in (getattr(x,'module','') or '') or 'hantu' in (getattr(x,'module','') or '') for x in ast.walk(n) if isinstance(x, ast.ImportFrom))]; print('IMPURE:', bad) if bad else print('pure ok')"`
Expected: `pure ok`

- [ ] **Step 3: Mark Phase 1 done in the spec**

In `docs/superpowers/specs/2026-06-20-infinite-buying-design.md`, update the `상태:` line to note Phase 1(도메인 코어 + 원장 영속화) 구현 완료, Phase 2(KIS 어댑터·서비스·스케줄·order_plan) 대기. Add a one-line pointer to `docs/superpowers/plans/2026-06-20-infinite-buying-phase1.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-06-20-infinite-buying-design.md
git commit -m "docs(infinite-buying): mark phase 1 (domain core + ledger) complete"
```

---

## Self-Review Notes

- **Spec coverage (Phase 1 범위):**
  - §3 별지점 → Task 1. §3 T·전반전/후반전 → Task 2. §4 회당금액(단리/반복리/복리) → Task 3.
  - §4~§5 체결 반영 평단·보유·누적액 재계산 + 쿼터매도 T≈0.75 + 사이클 종료 → Task 4.
  - §5 DB 모델(position/order/config) → Task 5 + 마이그레이션. 리포지토리 → Task 6.
  - **Phase 2로 이월(스펙 §9 리서치 의존):** order_plan 합성(첫매수/별지점/평단/여유매수 단 구성), KIS 어댑터(LOC/MOC/AFTER 지정가·체결조회), 서비스 오케스트레이션(place_daily_orders/reconcile_fills), 스케줄(발주/대조), 설정 API/UI, 전략 전용 계좌.
- **Type consistency:** `PositionState`(Task 4) ↔ 모델 `holding_qty/cumulative_buy`(Task 5) 명칭 일치. `Phase`(progress.py) 값 `first_half/second_half` ↔ position.phase 컬럼 코멘트 일치. `Compounding` 값 `simple/half/full` ↔ config.compounding 컬럼 코멘트·테스트 값 일치. `apply_sell` 반환 realized_profit ↔ Task 3 `update_per_round_amount(realized_profit=...)` 입력 연결.
- **No placeholders:** 모든 코드 스텝에 완전한 구현/테스트 포함. order_plan·서비스 등 미확정 부분은 stub로 넣지 않고 Phase 2로 명시 분리.
- **마이그레이션 주의:** Task 5 Step 7-8 — `alembic upgrade`는 호스트 확인·사용자 승인 후에만(prod 오적용 방지).
- **모델 위치 결정:** 스펙은 `src/infinite_buying/model.py`를 제안했으나, alembic autogenerate와 `Base.metadata`가 중앙 `models.py`를 스캔하는 코드베이스 관례를 따라 모델은 `src/database/models.py`에 둔다. 리포지토리는 bounded context 응집을 위해 모듈-로컬 유지.
