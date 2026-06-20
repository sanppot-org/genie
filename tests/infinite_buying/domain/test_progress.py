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
