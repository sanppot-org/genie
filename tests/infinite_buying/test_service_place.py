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
