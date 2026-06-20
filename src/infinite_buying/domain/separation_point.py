"""별지점 계산 (매수/매도를 가르는 기준점).

별지점 = 평단 * (1 + base * (1 - 2T/분할) / 100)
  - base_gap: 종목별 최대 괴리율(%포인트, 15는 15%를 의미하며 0.15가 아님)
  - T=0 → 평단*(1+base%), T=분할/2 → 평단
원전: docs/무한매수법.md §3.
"""


def separation_point(avg_price: float, t: float, division: int, base_gap: float) -> float:
    """평단·T·분할수·base 괴리율로 별지점을 계산한다.

    Args:
        avg_price: 평단가.
        t: 현재 T값 (매수누적액 / 회당금액).
        division: 분할수 (예: 40).
        base_gap: 종목별 최대 괴리율(%포인트). TQQQ=15, SOXL=20.

    Returns:
        별지점 가격.
    """
    return avg_price * (1 + base_gap * (1 - 2 * t / division) / 100)
