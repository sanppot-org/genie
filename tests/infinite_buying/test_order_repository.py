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
