"""회당금액(1회매수액) 갱신 — 수익 발생 시 복리 방식에 따라 증가.

- 단리(SIMPLE): 고정.
- 반복리(HALF, 기본): 회당금액 + 수익/2/분할수.
- 복리(FULL): 회당금액 + 수익/분할수.
예) 250불, 수익 80불, 40분할 → 반복리 251불, 복리 252불.
원전 §4는 "수익이 생길 때마다 회당금액이 증가한다"이므로, 손실(음수 차익) 매도는
회당금액을 줄이지 않는다(증가 전용). 원전: docs/무한매수법.md §4.
"""

from enum import StrEnum


class Compounding(StrEnum):
    """회당금액 갱신 방식."""

    SIMPLE = "simple"  # 단리: 고정
    HALF = "half"      # 반복리(기본)
    FULL = "full"      # 복리


def update_per_round_amount(
    current: float,
    realized_profit: float,
    division: int,
    mode: Compounding,
) -> float:
    """실현 수익을 반영해 회당금액을 갱신한다(증가 전용).

    Args:
        current: 현재 회당금액.
        realized_profit: 이번에 실현된 수익(매도 차익). 0 이하면 갱신 없음.
        division: 분할수.
        mode: 단리/반복리/복리.

    Returns:
        갱신된 회당금액.
    """
    if mode is Compounding.SIMPLE or realized_profit <= 0:
        return current
    if mode is Compounding.HALF:
        return current + realized_profit / 2 / division
    return current + realized_profit / division
