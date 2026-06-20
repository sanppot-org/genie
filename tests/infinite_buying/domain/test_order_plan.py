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
