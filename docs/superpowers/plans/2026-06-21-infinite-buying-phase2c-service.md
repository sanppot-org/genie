# 무한매수법 Phase 2c — 발주·대조 서비스 (스케줄러 제외) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 무한매수법 v1의 실거래 오케스트레이션을 구현한다 — `place_daily_orders`(발주잡: 계획→KIS 발주→원장 PENDING 기록)와 `reconcile_fills`(대조잡: 체결조회→원장 대조→평단·T·사이클 갱신). **스케줄러는 만들지 않는다**(수동 스크립트로만 실행 → 자동 발동 없음).

**Architecture:** 도메인(build_daily_plan, position_math, per_round_amount) + KIS 어댑터(Phase 2b) + 원장(Phase 1)을 잇는 서비스. 상태 변경은 **대조잡에서만** 발생(스펙 §4 불변식). 발주잡은 계획→발주→PENDING 기록만. 가격은 **raw close**(실거래 달러). 수동 실행: `scripts/`의 place/reconcile 스크립트.

**Tech Stack:** Python 3.12, SQLAlchemy, requests(mock in tests), Pydantic, pytest+pytest-mock, ruff, mypy, uv, dependency-injector.

**참조:** 스펙 §4(데이터흐름)·§10(v1 범위), Phase 1(원장·position_math), 2a(order_plan), 2b(KIS 어댑터). 결정(이 세션): 수동 스크립트, config 등록 스크립트만, raw close.

## Global Constraints

- **상태 변경은 reconcile_fills(대조잡)에서만.** place_daily_orders는 주문 발주 + `InfiniteBuyingOrder` PENDING 기록만; 포지션의 holding/cumulative/per_round/phase/realized는 건드리지 않는다(신규 사이클 position 행 생성은 예외 — 발주 전 활성 사이클이 없으면 cycle 1 생성).
- 가격: **raw close**(`stock_daily_candles.close`, adj 아님). 원장의 평단·별지점·실현손익 전부 실제 달러 기준.
- KIS 주문 가격 문자열: `f"{round(price, 2):.2f}"`(미국주식 2 decimal). MOC는 가격 없음.
- 거래소 매핑: `ticker.exchange`(KIS EXCD `NAS`/`NYS`/`AMS`) → 주문용 `OverseasExchangeCode`(`NAS`/`NYS`/`AMS` 미국 ETF는 주문 TR_ID 맵의 NASD/NYSE/AMEX로). 매핑: `{"NAS": NASD, "NYS": NYSE, "AMS": AMEX}`. **`ticker.exchange`가 None이면 그 종목은 발주 skip + 경고**(잘못된 거래소로 실주문 금지). 등록 스크립트(Task 4)가 exchange를 설정한다.
- intent→KIS 디스패치: buy+LOC→`buy_loc_order`; sell+quarter_sell+LOC→`sell_loc_order`; sell+quarter_sell+MOC→`sell_moc_order`; sell+limit_sell+LIMIT→`sell_limit_order`.
- 대조 매칭: 우리가 발주 시 저장한 `kis_order_no`(ODNO)로 `inquire_ccnl` 결과의 `odno`와 매칭. 체결수량 `ft_ccld_qty`, 체결단가 `ft_ccld_unpr3`.
- 체결 적용 순서: **매수 → 쿼터매도 → 지정가매도**(position_math 평단 일관성, 백테스트와 동일 규칙).
- 회당금액 갱신은 매도 실현수익으로 `update_per_round_amount(Compounding.HALF)`; `realized_pnl` 누적; `phase`는 `phase_of(calc_t(...))`로 재계산 저장. 전량 청산 시 position.status="closed" + `next_cycle_seed`로 다음 사이클 행 생성(per_round 이월).
- 모든 서비스 테스트는 KIS 어댑터(`HantuOverseasAPI`)를 mock, DB는 인메모리(conftest `db`/`session`). 실거래·실네트워크 호출 금지.
- enum/문자열 값은 모델 컬럼과 일치(side buy/sell, order_kind first_buy/separation_buy/avg_buy/quarter_sell/limit_sell, order_division LOC/MOC/LIMIT, status pending/filled/unfilled, position status active/closed, phase first_half/second_half).
- Python 3.12, ruff line-length 180, 룰 E,F,W,I,N,UP,ANN,B,A,C4(테스트 ANN001/201/202·N802 무시). mypy 통과.

---

## File Structure

- `src/infinite_buying/repository.py` (수정) — `InfiniteBuyingOrderRepository` 추가(Task 1).
- `src/infinite_buying/service.py` (생성) — `InfiniteBuyingService`(place_daily_orders, reconcile_fills) + 결과 dataclass + 헬퍼(Task 2, 3).
- `src/container.py` (수정) — 서비스 DI 등록(Task 4).
- `scripts/register_infinite_buying_config.py` (생성) — config 등록 + ticker.exchange 설정(Task 4).
- `scripts/run_infinite_buying.py` (생성) — place/reconcile 수동 실행(Task 4).
- 테스트: `tests/infinite_buying/test_order_repository.py`(Task 1), `tests/infinite_buying/test_service_place.py`(Task 2), `tests/infinite_buying/test_service_reconcile.py`(Task 3).

---

## Task 1: `InfiniteBuyingOrderRepository`

**Files:**
- Modify: `src/infinite_buying/repository.py`
- Test: `tests/infinite_buying/test_order_repository.py`

**Interfaces:**
- Consumes: `InfiniteBuyingOrder`(models), `BaseRepository`.
- Produces:
  - `InfiniteBuyingOrderRepository(session)`: `save(order) -> InfiniteBuyingOrder`(insert), `find_pending_by_position(position_id: int) -> list[InfiniteBuyingOrder]`, `find_by_kis_order_no(kis_order_no: str) -> InfiniteBuyingOrder | None`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/test_order_repository.py`:

```python
"""InfiniteBuyingOrderRepository 테스트 (인메모리)."""

from sqlalchemy.orm import Session

from src.database.models import InfiniteBuyingOrder
from src.infinite_buying.repository import InfiniteBuyingOrderRepository


def _order(position_id: int, odno: str, kind: str = "separation_buy", status: str = "pending") -> InfiniteBuyingOrder:
    return InfiniteBuyingOrder(
        position_id=position_id, kis_order_no=odno, side="buy", order_kind=kind,
        order_division="LOC", target_price=50.0, qty=4, status=status, filled_qty=0,
    )


def test_save_inserts_and_finds_pending(session: Session) -> None:
    repo = InfiniteBuyingOrderRepository(session)
    repo.save(_order(1, "A1"))
    repo.save(_order(1, "A2", status="filled"))
    repo.save(_order(2, "B1"))
    pending = repo.find_pending_by_position(1)
    assert {o.kis_order_no for o in pending} == {"A1"}  # filled 제외, 다른 position 제외


def test_find_by_kis_order_no(session: Session) -> None:
    repo = InfiniteBuyingOrderRepository(session)
    repo.save(_order(1, "ODNO123"))
    found = repo.find_by_kis_order_no("ODNO123")
    assert found is not None and found.position_id == 1
    assert repo.find_by_kis_order_no("NOPE") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/test_order_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'InfiniteBuyingOrderRepository'`

- [ ] **Step 3: Add the repository**

Append to `src/infinite_buying/repository.py` (add `InfiniteBuyingOrder` to the existing models import):

```python
class InfiniteBuyingOrderRepository(BaseRepository[InfiniteBuyingOrder, int]):
    """무한매수법 발주 원장 리포지토리. 발주잡이 PENDING 기록, 대조잡이 체결 갱신."""

    def _get_model_class(self) -> type[InfiniteBuyingOrder]:
        return InfiniteBuyingOrder

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("id",)

    def find_pending_by_position(self, position_id: int) -> list[InfiniteBuyingOrder]:
        """해당 포지션의 PENDING 주문 목록 (대조 대상)."""
        return (
            self.session.query(InfiniteBuyingOrder)
            .filter(
                InfiniteBuyingOrder.position_id == position_id,
                InfiniteBuyingOrder.status == "pending",
            )
            .order_by(InfiniteBuyingOrder.id)
            .all()
        )

    def find_by_kis_order_no(self, kis_order_no: str) -> InfiniteBuyingOrder | None:
        """KIS 주문번호로 조회."""
        return (
            self.session.query(InfiniteBuyingOrder)
            .filter(InfiniteBuyingOrder.kis_order_no == kis_order_no)
            .first()
        )
```

> 모델 import 줄을 `from src.database.models import InfiniteBuyingConfig, InfiniteBuyingOrder, InfiniteBuyingPosition`로 갱신.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/test_order_repository.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ tests/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/repository.py tests/infinite_buying/test_order_repository.py
git commit -m "feat(infinite-buying): add order ledger repository"
```

---

## Task 2: 발주 서비스 `place_daily_orders`

**Files:**
- Create: `src/infinite_buying/service.py`
- Test: `tests/infinite_buying/test_service_place.py`

**Interfaces:**
- Consumes: `Database`, `HantuOverseasAPI`(2b), repositories(Config/Position/Order), `TickerRepository`, `StockDailyCandleRepository`, `build_daily_plan`(2a), `PositionState`, `OverseasExchangeCode`.
- Produces:
  - `PlaceResult` (dataclass): `placed: int`, `skipped_no_exchange: list[str]`, `skipped_no_close: list[str]`, `tickers: int`
  - `InfiniteBuyingService(database, overseas_api)` with `place_daily_orders(now: date | None = None) -> PlaceResult`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/test_service_place.py`:

```python
"""place_daily_orders 발주잡 테스트 (KIS 어댑터 mock, 인메모리 DB)."""

from datetime import date
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import InfiniteBuyingConfig, StockDailyCandle, Ticker
from src.hantu.model.overseas import order as overseas_order
from src.infinite_buying.repository import (
    InfiniteBuyingOrderRepository,
    InfiniteBuyingPositionRepository,
)
from src.infinite_buying.service import InfiniteBuyingService


def _order_resp(odno: str) -> overseas_order.ResponseBody:
    return overseas_order.ResponseBody(
        rt_cd="0", msg_cd="MCA00000", msg1="ok",
        output=overseas_order.OrderOutput(KRX_FWDG_ORD_ORGNO="01790", ODNO=odno, ORD_TMD="092000"),
    )


def _seed(session: Session, *, exchange: str | None) -> int:
    t = Ticker(ticker="TQQQ", name="TQQQ", asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value, exchange=exchange)
    session.add(t)
    session.flush()
    session.add(InfiniteBuyingConfig(
        ticker_id=t.id, division=40, base_gap=15.0, allocation=10000.0,
        compounding="half", sell_limit_pct=15.0, active=True,
    ))
    session.add(StockDailyCandle(ticker_id=t.id, date=date(2026, 6, 18), open=50, high=52, low=49, close=50.0, volume=1000))
    session.flush()
    return t.id


def test_place_first_buy_creates_position_and_records_order(db: Database) -> None:
    api = MagicMock()
    api.buy_loc_order.return_value = _order_resp("ODNO_FB")
    with db.session_scope() as s:
        _seed(s, exchange="NAS")

    service = InfiniteBuyingService(database=db, overseas_api=api)
    result = service.place_daily_orders(now=date(2026, 6, 19))

    assert result.placed == 1 and result.tickers == 1
    # 첫매수 LOC 발주: 전일종가 50 → 목표가 57.5, qty floor(250/57.5)=4
    api.buy_loc_order.assert_called_once()
    args, kwargs = api.buy_loc_order.call_args
    assert "TQQQ" in args or kwargs.get("ticker") == "TQQQ"

    with db.session_scope() as s:
        pos = InfiniteBuyingPositionRepository(s).find_active_by_ticker(_only_ticker_id(s))
        assert pos is not None and pos.cycle_no == 1 and pos.holding_qty == 0  # 발주만, 상태 미변경
        orders = InfiniteBuyingOrderRepository(s).find_pending_by_position(pos.id)
        assert len(orders) == 1 and orders[0].kis_order_no == "ODNO_FB"
        assert orders[0].order_kind == "first_buy" and orders[0].status == "pending"


def test_place_skips_ticker_without_exchange(db: Database) -> None:
    api = MagicMock()
    with db.session_scope() as s:
        _seed(s, exchange=None)

    service = InfiniteBuyingService(database=db, overseas_api=api)
    result = service.place_daily_orders(now=date(2026, 6, 19))

    assert result.placed == 0
    assert "TQQQ" in result.skipped_no_exchange
    api.buy_loc_order.assert_not_called()


def _only_ticker_id(session: Session) -> int:
    return session.query(Ticker).filter(Ticker.ticker == "TQQQ").one().id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/test_service_place.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infinite_buying.service'`

- [ ] **Step 3: Write the implementation**

Create `src/infinite_buying/service.py`:

```python
"""무한매수법 실거래 오케스트레이션 (발주잡 + 대조잡).

place_daily_orders(발주잡): 활성 config별로 활성 사이클 보장 → 전일 raw 종가·상태 로드
→ build_daily_plan → KIS LOC/MOC/LIMIT 발주 → InfiniteBuyingOrder PENDING 기록(ODNO).
reconcile_fills(대조잡): inquire_ccnl 체결 대조 → position_math로 평단·T·사이클·회당금액·실현손익 갱신.

불변식: 포지션 상태 변경은 대조잡에서만(발주잡은 신규 사이클 행 생성·주문 기록만).
가격은 raw close(실거래 달러). 스케줄러 없음 — 수동 스크립트로 호출.
"""

from dataclasses import dataclass, field
from datetime import date

from src.database.database import Database
from src.database.models import InfiniteBuyingOrder, InfiniteBuyingPosition, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.hantu.model.overseas.exchange_code import OverseasExchangeCode
from src.hantu.overseas_api import HantuOverseasAPI
from src.infinite_buying.domain.order_plan import OrderIntent, build_daily_plan
from src.infinite_buying.domain.position_math import PositionState
from src.infinite_buying.repository import (
    InfiniteBuyingConfigRepository,
    InfiniteBuyingOrderRepository,
    InfiniteBuyingPositionRepository,
)

# ticker.exchange(KIS EXCD) → 주문용 OverseasExchangeCode (미국)
_EXCHANGE_MAP: dict[str, OverseasExchangeCode] = {
    "NAS": OverseasExchangeCode.NASD,
    "NYS": OverseasExchangeCode.NYSE,
    "AMS": OverseasExchangeCode.AMEX,
}


@dataclass
class PlaceResult:
    """발주잡 결과."""

    tickers: int = 0
    placed: int = 0
    skipped_no_exchange: list[str] = field(default_factory=list)
    skipped_no_close: list[str] = field(default_factory=list)


def _fmt_price(price: float) -> str:
    """KIS 주문 단가 문자열 (미국주식 2 decimal)."""
    return f"{round(price, 2):.2f}"


class InfiniteBuyingService:
    """무한매수법 발주·대조 서비스."""

    def __init__(self, database: Database, overseas_api: HantuOverseasAPI) -> None:
        self._database = database
        self._api = overseas_api

    def place_daily_orders(self, now: date | None = None) -> PlaceResult:
        """활성 종목별로 하루치 계획을 KIS에 발주하고 원장에 PENDING 기록."""
        today = now or date.today()
        result = PlaceResult()
        with self._database.session_scope() as session:
            configs = InfiniteBuyingConfigRepository(session).find_active()
            result.tickers = len(configs)
            for cfg in configs:
                ticker = session.query(Ticker).filter(Ticker.id == cfg.ticker_id).one()
                exchange = _EXCHANGE_MAP.get(ticker.exchange or "")
                if exchange is None:
                    result.skipped_no_exchange.append(ticker.ticker)
                    continue
                prev_close = self._latest_close(session, cfg.ticker_id, today)
                if prev_close is None:
                    result.skipped_no_close.append(ticker.ticker)
                    continue
                position = self._ensure_active_position(session, cfg.ticker_id, cfg.allocation, cfg.division)
                state = PositionState(holding_qty=position.holding_qty, cumulative_buy=position.cumulative_buy)
                plan = build_daily_plan(
                    state=state, per_round_amount=position.per_round_amount, prev_close=prev_close,
                    division=cfg.division, base_gap=cfg.base_gap, sell_limit_pct=cfg.sell_limit_pct,
                    allocation=cfg.allocation,
                )
                order_repo = InfiniteBuyingOrderRepository(session)
                for intent in plan:
                    odno = self._place_order(ticker.ticker, exchange, intent)
                    order_repo.save(InfiniteBuyingOrder(
                        position_id=position.id, kis_order_no=odno,
                        side=intent.side, order_kind=intent.order_kind, order_division=intent.order_division,
                        target_price=intent.target_price, qty=intent.qty, status="pending",
                        filled_qty=0, trade_date=today,
                    ))
                    result.placed += 1
        return result

    def _place_order(self, symbol: str, exchange: OverseasExchangeCode, intent: OrderIntent) -> str | None:
        """intent를 KIS 주문으로 발주하고 주문번호(ODNO)를 반환."""
        if intent.side == "buy":  # v1: 매수는 LOC만
            resp = self._api.buy_loc_order(symbol, intent.qty, _fmt_price(intent.target_price), exchange)
        elif intent.order_kind == "limit_sell":
            resp = self._api.sell_limit_order(symbol, intent.qty, _fmt_price(intent.target_price), exchange)
        elif intent.order_division == "MOC":
            resp = self._api.sell_moc_order(symbol, intent.qty, exchange)
        else:  # quarter_sell LOC
            resp = self._api.sell_loc_order(symbol, intent.qty, _fmt_price(intent.target_price), exchange)
        return resp.output.ODNO

    def _ensure_active_position(self, session: object, ticker_id: int, allocation: float, division: int) -> InfiniteBuyingPosition:
        """활성 사이클이 없으면 cycle 1을 생성해 반환."""
        repo = InfiniteBuyingPositionRepository(session)  # type: ignore[arg-type]
        existing = repo.find_active_by_ticker(ticker_id)
        if existing is not None:
            return existing
        per_round = allocation / division if division else 0.0
        return repo.save(InfiniteBuyingPosition(
            ticker_id=ticker_id, cycle_no=1, holding_qty=0, cumulative_buy=0.0,
            per_round_amount=per_round, phase="first_half", status="active", realized_pnl=0.0,
        ))

    @staticmethod
    def _latest_close(session: object, ticker_id: int, before: date) -> float | None:
        """before 이전 가장 최근 raw 종가 (전일종가)."""
        rows = StockDailyCandleRepository(session).find_by_ticker(ticker_id, to_date=before)  # type: ignore[arg-type]
        prior = [r for r in rows if r.date < before]
        return prior[-1].close if prior else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/test_service_place.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ tests/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/service.py tests/infinite_buying/test_service_place.py
git commit -m "feat(infinite-buying): add place_daily_orders service (order placement + ledger)"
```

---

## Task 3: 대조 서비스 `reconcile_fills`

**Files:**
- Modify: `src/infinite_buying/service.py` (메서드 + 결과 dataclass 추가)
- Test: `tests/infinite_buying/test_service_reconcile.py`

**Interfaces:**
- Consumes: `inquire_ccnl`(2b) → `list[execution.ExecutionRecord]`, position_math(`apply_buy`/`apply_sell`/`is_cycle_complete`/`next_cycle_seed`), `update_per_round_amount`/`Compounding`, `calc_t`/`phase_of`.
- Produces:
  - `ReconcileResult` (dataclass): `filled: int`, `cycles_closed: int`, `positions: int`
  - `InfiniteBuyingService.reconcile_fills(start_date: date, end_date: date) -> ReconcileResult`

- [ ] **Step 1: Write the failing test**

Create `tests/infinite_buying/test_service_reconcile.py`:

```python
"""reconcile_fills 대조잡 테스트 (inquire_ccnl mock, 인메모리 DB)."""

from datetime import date
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import (
    InfiniteBuyingConfig,
    InfiniteBuyingOrder,
    InfiniteBuyingPosition,
    Ticker,
)
from src.hantu.model.overseas.execution import ExecutionRecord
from src.infinite_buying.repository import (
    InfiniteBuyingOrderRepository,
    InfiniteBuyingPositionRepository,
)
from src.infinite_buying.service import InfiniteBuyingService


def _rec(odno: str, sll_buy: str, ccld_qty: str, unpr: str) -> ExecutionRecord:
    return ExecutionRecord(
        ord_dt="20260619", odno=odno, pdno="TQQQ", sll_buy_dvsn_cd=sll_buy,
        ft_ord_qty=ccld_qty, ft_ccld_qty=ccld_qty, ft_ccld_unpr3=unpr, nccs_qty="0",
        prcs_stat_name="체결", ord_tmd="160000", ovrs_excg_cd="NASD",
    )


def _seed_position_with_pending_buy(session: Session) -> int:
    t = Ticker(ticker="TQQQ", name="TQQQ", asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value, exchange="NAS")
    session.add(t)
    session.flush()
    session.add(InfiniteBuyingConfig(ticker_id=t.id, division=40, base_gap=15.0, allocation=10000.0, compounding="half", sell_limit_pct=15.0, active=True))
    pos = InfiniteBuyingPosition(ticker_id=t.id, cycle_no=1, holding_qty=0, cumulative_buy=0.0, per_round_amount=250.0, phase="first_half", status="active", realized_pnl=0.0)
    session.add(pos)
    session.flush()
    session.add(InfiniteBuyingOrder(position_id=pos.id, kis_order_no="ODNO_FB", side="buy", order_kind="first_buy", order_division="LOC", target_price=57.5, qty=4, status="pending", filled_qty=0))
    session.flush()
    return t.id


def test_reconcile_applies_buy_fill_to_position(db: Database) -> None:
    api = MagicMock()
    api.inquire_ccnl.return_value = [_rec("ODNO_FB", "02", "4", "50.00")]  # 매수 4주 @50 체결
    with db.session_scope() as s:
        ticker_id = _seed_position_with_pending_buy(s)

    service = InfiniteBuyingService(database=db, overseas_api=api)
    result = service.reconcile_fills(date(2026, 6, 19), date(2026, 6, 19))

    assert result.filled == 1
    with db.session_scope() as s:
        pos = InfiniteBuyingPositionRepository(s).find_active_by_ticker(ticker_id)
        assert pos.holding_qty == 4
        assert pos.cumulative_buy == 200.0  # 4*50
        order = InfiniteBuyingOrderRepository(s).find_by_kis_order_no("ODNO_FB")
        assert order.status == "filled" and order.filled_qty == 4 and order.filled_price == 50.0


def test_reconcile_full_liquidation_closes_cycle_and_seeds_next(db: Database) -> None:
    api = MagicMock()
    # 보유 4주를 지정가매도로 전량 청산 (체결 @60)
    api.inquire_ccnl.return_value = [_rec("ODNO_SELL", "01", "4", "60.00")]
    with db.session_scope() as s:
        t = Ticker(ticker="TQQQ", name="TQQQ", asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value, exchange="NAS")
        s.add(t); s.flush()
        s.add(InfiniteBuyingConfig(ticker_id=t.id, division=40, base_gap=15.0, allocation=10000.0, compounding="half", sell_limit_pct=15.0, active=True))
        pos = InfiniteBuyingPosition(ticker_id=t.id, cycle_no=1, holding_qty=4, cumulative_buy=200.0, per_round_amount=250.0, phase="first_half", status="active", realized_pnl=0.0)
        s.add(pos); s.flush()
        s.add(InfiniteBuyingOrder(position_id=pos.id, kis_order_no="ODNO_SELL", side="sell", order_kind="limit_sell", order_division="LIMIT", target_price=57.5, qty=4, status="pending", filled_qty=0))
        s.flush()
        ticker_id = t.id

    service = InfiniteBuyingService(database=db, overseas_api=api)
    result = service.reconcile_fills(date(2026, 6, 19), date(2026, 6, 19))

    assert result.cycles_closed == 1
    with db.session_scope() as s:
        active = InfiniteBuyingPositionRepository(s).find_active_by_ticker(ticker_id)
        assert active is not None and active.cycle_no == 2 and active.holding_qty == 0  # 새 사이클
        # 실현수익 (60-50)*4=40 → 반복리 회당금액 250 + 40/2/40 = 250.5 이월
        assert active.per_round_amount == 250.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infinite_buying/test_service_reconcile.py -v`
Expected: FAIL with `AttributeError: 'InfiniteBuyingService' object has no attribute 'reconcile_fills'`

- [ ] **Step 3: Write the implementation**

Add to `src/infinite_buying/service.py` — new imports, `ReconcileResult`, and the method. Imports to add:

```python
from src.infinite_buying.domain.per_round_amount import Compounding, update_per_round_amount
from src.infinite_buying.domain.position_math import (
    apply_buy,
    apply_sell,
    is_cycle_complete,
    next_cycle_seed,
)
from src.infinite_buying.domain.progress import calc_t, phase_of
```

Add the result dataclass near `PlaceResult`:

```python
@dataclass
class ReconcileResult:
    """대조잡 결과."""

    positions: int = 0
    filled: int = 0
    cycles_closed: int = 0
```

Add these methods to `InfiniteBuyingService`:

```python
    def reconcile_fills(self, start_date: date, end_date: date) -> ReconcileResult:
        """KIS 체결조회로 PENDING 주문을 대조해 평단·T·사이클·회당금액을 갱신한다."""
        result = ReconcileResult()
        with self._database.session_scope() as session:
            configs = InfiniteBuyingConfigRepository(session).find_active()
            pos_repo = InfiniteBuyingPositionRepository(session)
            for cfg in configs:
                position = pos_repo.find_active_by_ticker(cfg.ticker_id)
                if position is None:
                    continue
                pending = InfiniteBuyingOrderRepository(session).find_pending_by_position(position.id)
                if not pending:
                    continue
                ticker = session.query(Ticker).filter(Ticker.id == cfg.ticker_id).one()
                exchange = _EXCHANGE_MAP.get(ticker.exchange or "")
                if exchange is None:
                    continue
                records = self._api.inquire_ccnl(start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), exchange)
                by_odno = {r.odno: r for r in records}
                result.positions += 1
                if self._apply_fills(session, cfg, position, pending, by_odno, result, end_date):
                    result.cycles_closed += 1
        return result

    def _apply_fills(
        self,
        session: object,
        cfg: object,
        position: InfiniteBuyingPosition,
        pending: list[InfiniteBuyingOrder],
        by_odno: dict[str, object],
        result: ReconcileResult,
        trade_date: date,
    ) -> bool:
        """PENDING 주문에 체결을 반영(매수→쿼터매도→지정가매도). 사이클 종료 시 True."""
        state = PositionState(holding_qty=position.holding_qty, cumulative_buy=position.cumulative_buy)
        per_round = position.per_round_amount
        realized_total = position.realized_pnl
        for order in _sorted_for_apply(pending):
            rec = by_odno.get(order.kis_order_no or "")
            if rec is None:
                continue  # 이번 조회창에 없음 → PENDING 유지
            ccld = int(rec.ft_ccld_qty)
            if ccld <= 0:
                order.status = "unfilled"
                continue
            price = float(rec.ft_ccld_unpr3)
            if order.side == "buy":
                state = apply_buy(state, price, ccld)
            else:
                state, realized = apply_sell(state, price, ccld)
                per_round = update_per_round_amount(per_round, realized, cfg.division, Compounding.HALF)  # type: ignore[attr-defined]
                realized_total += realized
            order.status = "filled"
            order.filled_qty = ccld
            order.filled_price = price
            order.trade_date = trade_date
            result.filled += 1

        position.holding_qty = state.holding_qty
        position.cumulative_buy = state.cumulative_buy
        position.per_round_amount = per_round
        position.realized_pnl = realized_total
        position.phase = phase_of(calc_t(state.cumulative_buy, per_round), cfg.division).value  # type: ignore[attr-defined]

        if is_cycle_complete(state):
            position.status = "closed"
            _seed_state, next_no = next_cycle_seed(position.cycle_no)
            InfiniteBuyingPositionRepository(session).save(InfiniteBuyingPosition(  # type: ignore[arg-type]
                ticker_id=position.ticker_id, cycle_no=next_no, holding_qty=0, cumulative_buy=0.0,
                per_round_amount=per_round, phase="first_half", status="active", realized_pnl=0.0,
            ))
            return True
        return False
```

Add the module-level helper (near `_fmt_price`):

```python
def _sorted_for_apply(orders: list[InfiniteBuyingOrder]) -> list[InfiniteBuyingOrder]:
    """체결 적용 순서: 매수 → 쿼터매도 → 지정가매도 (평단 일관성)."""
    rank = {"buy": 0, "quarter_sell": 1, "limit_sell": 2}
    return sorted(orders, key=lambda o: rank.get(o.order_kind if o.side == "sell" else "buy", 0))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infinite_buying/test_service_reconcile.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/infinite_buying/ tests/infinite_buying/ && uv run mypy src/infinite_buying/
git add src/infinite_buying/service.py tests/infinite_buying/test_service_reconcile.py
git commit -m "feat(infinite-buying): add reconcile_fills service (fill matching + state update)"
```

---

## Task 4: DI 등록 + 스크립트(config 등록, place/reconcile 실행)

**Files:**
- Modify: `src/container.py`
- Create: `scripts/register_infinite_buying_config.py`
- Create: `scripts/run_infinite_buying.py`

**Interfaces:**
- Produces: DI provider `infinite_buying_service`; 두 스크립트(CLI).

- [ ] **Step 1: Register the service in DI**

In `src/container.py`, add import near other service imports:

```python
from src.infinite_buying.service import InfiniteBuyingService
```

and add a provider after `hantu_overseas_api` (uses `database` + `hantu_overseas_api` providers):

```python
    infinite_buying_service = providers.Factory(
        InfiniteBuyingService,
        database=database,
        overseas_api=hantu_overseas_api,
    )
```

- [ ] **Step 2: Verify the container builds**

Run: `uv run python -c "from src.container import ApplicationContainer; c=ApplicationContainer(); print(c.infinite_buying_service)"`
Expected: provider 객체 출력(에러 없음).

- [ ] **Step 3: Create the config registration script**

Create `scripts/register_infinite_buying_config.py`:

```python
"""무한매수법 종목 설정 등록 스크립트.

사용:
    ENV_PROFILE=local uv run python scripts/register_infinite_buying_config.py \
        --ticker TQQQ --exchange NAS --base-gap 15 --sell-limit-pct 15 --allocation 10000 --division 40

ticker.exchange(KIS EXCD: NAS/NYS/AMS)를 설정하고 infinite_buying_config를 upsert한다.
선행: 해당 ticker가 tickers에 등록돼 있어야 함(register_us_tickers.py).
"""

import argparse
import logging

from src.container import ApplicationContainer
from src.database.models import InfiniteBuyingConfig
from src.database.ticker_repository import TickerRepository
from src.infinite_buying.repository import InfiniteBuyingConfigRepository

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register infinite-buying config for a ticker.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--exchange", required=True, choices=["NAS", "NYS", "AMS"], help="KIS EXCD")
    parser.add_argument("--base-gap", type=float, required=True)
    parser.add_argument("--sell-limit-pct", type=float, default=None)
    parser.add_argument("--allocation", type=float, default=10000.0)
    parser.add_argument("--division", type=int, default=40)
    parser.add_argument("--compounding", default="half", choices=["simple", "half", "full"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sell_limit_pct = args.sell_limit_pct if args.sell_limit_pct is not None else args.base_gap

    database = ApplicationContainer().database()
    with database.session_scope() as session:
        ticker = TickerRepository(session).find_by_ticker(args.ticker)
        if ticker is None or ticker.id is None:
            raise SystemExit(f"티커 미등록: {args.ticker} (register_us_tickers.py로 먼저 등록)")
        ticker.exchange = args.exchange  # 거래소코드 설정(실주문 필수)
        InfiniteBuyingConfigRepository(session).save(InfiniteBuyingConfig(
            ticker_id=ticker.id, division=args.division, base_gap=args.base_gap,
            allocation=args.allocation, compounding=args.compounding,
            sell_limit_pct=sell_limit_pct, active=True,
        ))
    logger.info("무한매수법 설정 등록 완료: %s (exchange=%s, base_gap=%s, div=%d)", args.ticker, args.exchange, args.base_gap, args.division)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create the run script**

Create `scripts/run_infinite_buying.py`:

```python
"""무한매수법 발주/대조 수동 실행 스크립트 (스케줄러 없음).

사용:
    # 발주(미국장 마감 직전): 오늘 걸 주문을 KIS에 발주
    ENV_PROFILE=local uv run python scripts/run_infinite_buying.py place
    # 대조(다음날): 전일 체결을 원장에 반영
    ENV_PROFILE=local uv run python scripts/run_infinite_buying.py reconcile --start 20260619 --end 20260619

⚠️ place는 실계좌에 실제 주문을 발주한다(REAL 계좌·실거래). 대상 계좌·환경을 반드시 확인하고 실행할 것.
"""

import argparse
from datetime import date, datetime
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run infinite-buying place/reconcile manually.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("place", help="오늘치 주문 발주")
    rec = sub.add_parser("reconcile", help="체결 대조")
    rec.add_argument("--start", required=True, help="YYYYMMDD")
    rec.add_argument("--end", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    service = ApplicationContainer().infinite_buying_service()

    if args.cmd == "place":
        result = service.place_daily_orders()
        logger.info(
            "발주 완료: 종목 %d, 발주 %d, exchange 누락 skip=%s, 종가 누락 skip=%s",
            result.tickers, result.placed, result.skipped_no_exchange, result.skipped_no_close,
        )
    else:
        start = datetime.strptime(args.start, "%Y%m%d").date()
        end = datetime.strptime(args.end, "%Y%m%d").date()
        result = service.reconcile_fills(start, end)
        logger.info("대조 완료: 포지션 %d, 체결반영 %d, 사이클종료 %d", result.positions, result.filled, result.cycles_closed)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Smoke-test scripts + lint**

Run: `uv run python -c "import ast; [ast.parse(open(f).read()) for f in ['scripts/register_infinite_buying_config.py','scripts/run_infinite_buying.py']]; print('ok')"`
Expected: `ok`

Run: `uv run python scripts/run_infinite_buying.py --help && uv run python scripts/register_infinite_buying_config.py --help`
Expected: usage 출력(에러 없음).

Run: `uv run ruff check src/container.py scripts/register_infinite_buying_config.py scripts/run_infinite_buying.py && uv run mypy src/`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/container.py scripts/register_infinite_buying_config.py scripts/run_infinite_buying.py
git commit -m "feat(infinite-buying): wire service into DI + add config/run scripts (no scheduler)"
```

---

## Self-Review Notes

- **Spec coverage:** §4 발주잡(계획→발주→PENDING 기록) Task 2, 대조잡(체결조회→상태갱신→사이클) Task 3. §10 v1(정규장 LOC/MOC/LIMIT, raw close, 공용계좌+ODNO 매칭). 주문 리포지토리 Task 1(Phase 1서 이월). 스케줄러는 명시적 제외(수동 스크립트 Task 4).
- **불변식:** 상태 변경은 reconcile_fills에서만(place는 신규 사이클 행 생성·주문 기록만). 체결 적용 순서 매수→쿼터→지정가(`_sorted_for_apply`). 백테스트와 동일 규칙.
- **Type consistency:** OrderIntent(2a)·position_math(1)·execution.ExecutionRecord(2b)·ledger 모델(1)·order 메서드(2b) 시그니처 그대로 소비. `_EXCHANGE_MAP`로 ticker.exchange→OverseasExchangeCode.
- **안전장치:** ticker.exchange None이면 발주 skip(잘못된 거래소 실주문 방지). prev_close 없으면 skip. 모의투자는 LOC/MOC 불가(REAL 전제) — 스크립트에 실거래 경고 명시.
- **No placeholders:** 전 태스크 완전 코드/테스트. 테스트는 KIS mock + 인메모리 DB, 실네트워크/실주문 없음.
- **알려진 한계:** 주문 정정/취소 없음(fire-and-forget); 가격 2-decimal 포맷(틱사이즈 단순화); inquire_ccnl을 종목별 호출(소수 종목 가정); place는 멱등 아님(같은 날 두 번 호출 시 중복 발주 — 운영상 1일 1회 호출 전제). DI/세션 타입 힌트는 object+ignore로 단순화(런타임 정상).
- **실행 안전:** 스케줄러 없음 → 자동 발동 불가. place는 REAL 계좌 실주문이므로 운영 투입 전 별도 검증 필요(이 플랜 범위 밖).
