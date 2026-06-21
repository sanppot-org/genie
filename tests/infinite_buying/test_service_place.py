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


def test_place_sell_routing_calls_correct_api_and_records_orders(db: Database) -> None:
    """전반전 매도 경로: quarter_sell→LOC, limit_sell→LIMIT. 포지션 상태 미변경 확인."""
    api = MagicMock()
    api.buy_loc_order.return_value = _order_resp("ODNO_BUY")
    api.sell_loc_order.return_value = _order_resp("ODNO_QLOC")
    api.sell_limit_order.return_value = _order_resp("ODNO_LMT")

    with db.session_scope() as s:
        from src.database.models import InfiniteBuyingPosition
        ticker_id = _seed(s, exchange="NAS")
        # 기존 활성 포지션: holding_qty=16, cumulative_buy=740.0 → 전반전, 매수 가능
        s.add(InfiniteBuyingPosition(
            ticker_id=ticker_id, cycle_no=1,
            holding_qty=16, cumulative_buy=740.0,
            per_round_amount=250.0, phase="first_half",
            status="active", realized_pnl=0.0,
        ))

    service = InfiniteBuyingService(database=db, overseas_api=api)
    result = service.place_daily_orders(now=date(2026, 6, 19))

    # 전반전: buy × 2 (separation_buy + avg_buy) + sell × 2 (quarter_sell LOC + limit_sell LIMIT)
    assert result.placed == 4

    api.sell_loc_order.assert_called()   # quarter_sell → LOC
    api.sell_limit_order.assert_called()  # limit_sell  → LIMIT

    with db.session_scope() as s:
        pos = InfiniteBuyingPositionRepository(s).find_active_by_ticker(_only_ticker_id(s))
        assert pos is not None
        # 발주잡은 포지션 상태를 변경하지 않는다
        assert pos.holding_qty == 16
        assert pos.cumulative_buy == 740.0

        orders = InfiniteBuyingOrderRepository(s).find_pending_by_position(pos.id)
        kinds = {o.order_kind: o for o in orders}

        assert kinds["quarter_sell"].order_division == "LOC"
        assert kinds["limit_sell"].order_division == "LIMIT"


def _only_ticker_id(session: Session) -> int:
    return session.query(Ticker).filter(Ticker.ticker == "TQQQ").one().id
