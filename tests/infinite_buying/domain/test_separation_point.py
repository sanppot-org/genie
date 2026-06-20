"""별지점 공식 검산 (docs/무한매수법.md §3)."""

import pytest

from src.infinite_buying.domain.separation_point import separation_point


def test_t_zero_returns_avg_times_full_base() -> None:
    # T=0 → 평단 * (1 + base%)
    assert separation_point(avg_price=100.0, t=0.0, division=40, base_gap=15.0) == pytest.approx(115.0)


def test_t_half_division_returns_avg() -> None:
    # T = 분할/2 → 정확히 평단
    assert separation_point(avg_price=100.0, t=20.0, division=40, base_gap=15.0) == pytest.approx(100.0)


def test_tqqq_40div_midpoint() -> None:
    # TQQQ base=15, 40분할, T=10 → 15*(1-20/40)=7.5 → 평단*1.075
    assert separation_point(avg_price=100.0, t=10.0, division=40, base_gap=15.0) == pytest.approx(107.5)


def test_soxl_base_20_t_zero() -> None:
    # SOXL base=20, T=0 → 평단*1.20
    assert separation_point(avg_price=50.0, t=0.0, division=40, base_gap=20.0) == pytest.approx(60.0)
