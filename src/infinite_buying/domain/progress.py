"""진행도(T)와 전반전/후반전 판정.

T = 매수누적액 / 회당금액(현재). 회차가 분할/2 미만이면 전반전, 이상이면 후반전.
원전: docs/무한매수법.md §3~§4.
"""

from enum import StrEnum


class Phase(StrEnum):
    """전반전/후반전 구분."""

    FIRST_HALF = "first_half"    # T < 분할/2
    SECOND_HALF = "second_half"  # T >= 분할/2


def calc_t(cumulative_buy: float, per_round_amount: float) -> float:
    """T = 매수누적액 / 회당금액. 회당금액이 0 이하면 0.0."""
    if per_round_amount <= 0:
        return 0.0
    return cumulative_buy / per_round_amount


def phase_of(t: float, division: int) -> Phase:
    """T와 분할수로 전반전/후반전 판정 (T >= 분할/2 → 후반전)."""
    return Phase.SECOND_HALF if t >= division / 2 else Phase.FIRST_HALF
