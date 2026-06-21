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
    session.add(InfiniteBuyingOrder(
        position_id=pos.id, kis_order_no="ODNO_FB", side="buy", order_kind="first_buy",
        order_division="LOC", target_price=57.5, qty=4, status="pending", filled_qty=0,
    ))
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
        assert order.trade_date == date(2026, 6, 19)
        # T = cumulative_buy / per_round = 200 / 250 = 0.8; half = division/2 = 20; 0.8 < 20 → first_half
        assert pos.phase == "first_half"


def test_reconcile_full_liquidation_closes_cycle_and_seeds_next(db: Database) -> None:
    api = MagicMock()
    # 보유 4주를 지정가매도로 전량 청산 (체결 @60)
    api.inquire_ccnl.return_value = [_rec("ODNO_SELL", "01", "4", "60.00")]
    with db.session_scope() as s:
        t = Ticker(ticker="TQQQ", name="TQQQ", asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value, exchange="NAS")
        s.add(t)
        s.flush()
        s.add(InfiniteBuyingConfig(ticker_id=t.id, division=40, base_gap=15.0, allocation=10000.0, compounding="half", sell_limit_pct=15.0, active=True))
        pos = InfiniteBuyingPosition(ticker_id=t.id, cycle_no=1, holding_qty=4, cumulative_buy=200.0, per_round_amount=250.0, phase="first_half", status="active", realized_pnl=0.0)
        s.add(pos)
        s.flush()
        s.add(InfiniteBuyingOrder(
            position_id=pos.id, kis_order_no="ODNO_SELL", side="sell", order_kind="limit_sell",
            order_division="LIMIT", target_price=57.5, qty=4, status="pending", filled_qty=0,
        ))
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
