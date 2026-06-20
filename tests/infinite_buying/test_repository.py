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
