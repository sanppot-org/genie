"""회당금액 갱신 (단리/반복리/복리) — docs/무한매수법.md §4."""

import pytest

from src.infinite_buying.domain.per_round_amount import Compounding, update_per_round_amount


def test_simple_keeps_amount_fixed() -> None:
    assert update_per_round_amount(250.0, realized_profit=80.0, division=40, mode=Compounding.SIMPLE) == 250.0


def test_half_adds_profit_over_two_division() -> None:
    # 반복리(기본): 회당금액 + 수익/2/분할수 → 250 + 80/2/40 = 251
    assert update_per_round_amount(250.0, realized_profit=80.0, division=40, mode=Compounding.HALF) == pytest.approx(251.0)


def test_full_adds_profit_over_division() -> None:
    # 복리: 회당금액 + 수익/분할수 → 250 + 80/40 = 252
    assert update_per_round_amount(250.0, realized_profit=80.0, division=40, mode=Compounding.FULL) == pytest.approx(252.0)


def test_loss_does_not_reduce_amount() -> None:
    # 원전 §4: "수익이 생길 때마다 증가" — 손실(음수 차익) 매도는 회당금액을 줄이지 않는다.
    assert update_per_round_amount(250.0, realized_profit=-80.0, division=40, mode=Compounding.HALF) == 250.0
    assert update_per_round_amount(250.0, realized_profit=-80.0, division=40, mode=Compounding.FULL) == 250.0
