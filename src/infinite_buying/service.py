"""무한매수법 실거래 오케스트레이션 (발주잡 + 대조잡).

place_daily_orders(발주잡): 활성 config별로 활성 사이클 보장 → 전일 raw 종가·상태 로드
→ build_daily_plan → KIS LOC/MOC/LIMIT 발주 → InfiniteBuyingOrder PENDING 기록(ODNO).
reconcile_fills(대조잡): inquire_ccnl 체결 대조 → position_math로 평단·T·사이클·회당금액·실현손익 갱신.

불변식: 포지션 상태 변경은 대조잡에서만(발주잡은 신규 사이클 행 생성·주문 기록만).
가격은 raw close(실거래 달러). 스케줄러 없음 — 수동 스크립트로 호출.
"""

from dataclasses import dataclass, field
from datetime import date
import logging

from sqlalchemy.orm import Session

from src.database.database import Database
from src.database.models import InfiniteBuyingConfig, InfiniteBuyingOrder, InfiniteBuyingPosition, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.hantu.model.overseas.exchange_code import OverseasExchangeCode
from src.hantu.model.overseas.execution import ExecutionRecord
from src.hantu.overseas_api import HantuOverseasAPI
from src.infinite_buying.domain.order_plan import OrderIntent, build_daily_plan
from src.infinite_buying.domain.per_round_amount import Compounding, update_per_round_amount
from src.infinite_buying.domain.position_math import (
    PositionState,
    apply_buy,
    apply_sell,
    is_cycle_complete,
    next_cycle_seed,
)
from src.infinite_buying.domain.progress import calc_t, phase_of
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

logger = logging.getLogger(__name__)


@dataclass
class PlaceResult:
    """발주잡 결과."""

    tickers: int = 0
    placed: int = 0
    skipped_no_exchange: list[str] = field(default_factory=list)
    skipped_no_close: list[str] = field(default_factory=list)
    skipped_already_placed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class ReconcileResult:
    """대조잡 결과."""

    positions: int = 0
    filled: int = 0
    cycles_closed: int = 0


def _fmt_price(price: float) -> str:
    """KIS 주문 단가 문자열 (미국주식 2 decimal)."""
    return f"{round(price, 2):.2f}"


def _sorted_for_apply(orders: list[InfiniteBuyingOrder]) -> list[InfiniteBuyingOrder]:
    """체결 적용 순서: 매수 → 쿼터매도 → 지정가매도 (평단 일관성)."""
    rank = {"buy": 0, "quarter_sell": 1, "limit_sell": 2}
    return sorted(orders, key=lambda o: rank.get(o.order_kind if o.side == "sell" else "buy", 99))


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
                order_repo = InfiniteBuyingOrderRepository(session)
                # 멱등성: 같은 날 이미 발주했으면 재발주 금지 (실주문 중복 방지)
                if order_repo.exists_for_position_on_date(position.id, today):
                    result.skipped_already_placed.append(ticker.ticker)
                    continue
                state = PositionState(holding_qty=position.holding_qty, cumulative_buy=position.cumulative_buy)
                plan = build_daily_plan(
                    state=state, per_round_amount=position.per_round_amount, prev_close=prev_close,
                    division=cfg.division, base_gap=cfg.base_gap, sell_limit_pct=cfg.sell_limit_pct,
                    allocation=cfg.allocation,
                )
                for intent in plan:
                    # intent별 예외 격리: N+1 주문이 실패해도 이미 체결된 N..1 원장 행은 커밋되어야
                    # 대조잡이 매칭할 수 있다. 예외가 session_scope 밖으로 새면 전체 롤백 → 상태 드리프트.
                    # 잔여 리스크: KIS가 주문을 수락했으나 응답이 에러(ODNO 없음)면 기록 불가 —
                    # fire-and-forget의 본질적 한계로 본 범위 밖.
                    try:
                        odno = self._place_order(ticker.ticker, exchange, intent)
                        order_repo.save(InfiniteBuyingOrder(
                            position_id=position.id, kis_order_no=odno,
                            side=intent.side, order_kind=intent.order_kind, order_division=intent.order_division,
                            target_price=intent.target_price, qty=intent.qty, status="pending",
                            filled_qty=0, trade_date=today,
                        ))
                        result.placed += 1
                    except Exception:
                        logger.exception("발주 실패 ticker=%s kind=%s", ticker.ticker, intent.order_kind)
                        result.failed.append(f"{ticker.ticker}:{intent.order_kind}")
                        continue
        return result

    def _place_order(self, symbol: str, exchange: OverseasExchangeCode, intent: OrderIntent) -> str:
        """intent를 KIS 주문으로 발주하고 주문번호(ODNO)를 반환."""
        if intent.side == "buy":  # v1: 매수는 LOC만
            resp = self._api.buy_loc_order(symbol, intent.qty, _fmt_price(intent.target_price), exchange)
        elif intent.order_kind == "limit_sell" and intent.order_division == "LIMIT":
            resp = self._api.sell_limit_order(symbol, intent.qty, _fmt_price(intent.target_price), exchange)
        elif intent.order_division == "MOC":
            resp = self._api.sell_moc_order(symbol, intent.qty, exchange)
        else:  # quarter_sell LOC
            resp = self._api.sell_loc_order(symbol, intent.qty, _fmt_price(intent.target_price), exchange)
        # validate_response가 rt_cd!=0에서 예외를 던지므로 성공 응답은 항상 ODNO를 가진다.
        assert resp.output.ODNO, "KIS 주문 응답에 ODNO 없음"
        return resp.output.ODNO

    def _ensure_active_position(self, session: Session, ticker_id: int, allocation: float, division: int) -> InfiniteBuyingPosition:
        """활성 사이클이 없으면 cycle 1을 생성해 반환."""
        repo = InfiniteBuyingPositionRepository(session)
        existing = repo.find_active_by_ticker(ticker_id)
        if existing is not None:
            return existing
        per_round = allocation / division if division else 0.0
        return repo.save(InfiniteBuyingPosition(
            ticker_id=ticker_id, cycle_no=1, holding_qty=0, cumulative_buy=0.0,
            per_round_amount=per_round, phase="first_half", status="active", realized_pnl=0.0,
        ))

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
        session: Session,
        cfg: InfiniteBuyingConfig,
        position: InfiniteBuyingPosition,
        pending: list[InfiniteBuyingOrder],
        by_odno: dict[str, ExecutionRecord],
        result: ReconcileResult,
        trade_date: date,
    ) -> bool:
        """PENDING 주문에 체결을 반영(매수→쿼터매도→지정가매도). 사이클 종료 시 True."""
        # 사이클 종료 판단에 사용: 적용 전 보유 수량이 있었는지. 신규 시드 사이클(보유 0)에서
        # 첫매수가 미체결이면 holding 0이 유지되는데, 이를 청산으로 오인해 사이클을 닫으면 안 된다.
        had_holding = position.holding_qty > 0
        state = PositionState(holding_qty=position.holding_qty, cumulative_buy=position.cumulative_buy)
        per_round = position.per_round_amount
        realized_total = position.realized_pnl
        compounding = Compounding(cfg.compounding)
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
                per_round = update_per_round_amount(per_round, realized, cfg.division, compounding)
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

        if had_holding and is_cycle_complete(state):
            position.status = "closed"
            _seed_state, next_no = next_cycle_seed(position.cycle_no)
            InfiniteBuyingPositionRepository(session).save(InfiniteBuyingPosition(
                ticker_id=position.ticker_id, cycle_no=next_no, holding_qty=0, cumulative_buy=0.0,
                per_round_amount=per_round, phase="first_half", status="active", realized_pnl=0.0,
            ))
            return True
        return False

    @staticmethod
    def _latest_close(session: Session, ticker_id: int, before: date) -> float | None:
        """before 이전 가장 최근 raw 종가 (전일종가)."""
        # find_by_ticker returns rows ordered by date ascending, so prior[-1] is the most recent close.
        rows = StockDailyCandleRepository(session).find_by_ticker(ticker_id, to_date=before)
        prior = [r for r in rows if r.date < before]
        return prior[-1].close if prior else None
