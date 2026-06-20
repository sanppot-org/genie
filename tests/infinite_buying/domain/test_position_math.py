"""체결 반영 평단·보유·매수누적액 재계산 (docs/무한매수법.md §4~§5)."""

import pytest

from src.infinite_buying.domain.position_math import (
    PositionState,
    apply_buy,
    apply_sell,
    is_cycle_complete,
    next_cycle_seed,
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


def test_oversell_clamps_holding_to_zero() -> None:
    # 비정상 입력(매도수량 > 보유수량)이라도 보유수량이 음수가 되지 않는다.
    s = PositionState(holding_qty=3, cumulative_buy=150.0)
    new_state, _ = apply_sell(s, fill_price=60.0, fill_qty=5)
    assert new_state.holding_qty == 0
    assert new_state.cumulative_buy == pytest.approx(0.0)


def test_next_cycle_seed_resets_state_and_increments_cycle() -> None:
    seed_state, next_no = next_cycle_seed(prev_cycle_no=1)
    assert seed_state == PositionState(holding_qty=0, cumulative_buy=0.0)
    assert next_no == 2
