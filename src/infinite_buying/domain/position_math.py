"""체결 1건을 반영해 포지션 상태(평단·보유수량·매수누적액)를 재계산한다.

불변식: 평단 = 매수누적액 / 보유수량. 매도는 평단을 바꾸지 않고
매수누적액을 평단×매도수량만큼 비례 감소시킨다(→ T 비례 하락, 쿼터매도 시 ≈0.75배).
매도 차익(realized profit)은 회당금액 갱신(per_round_amount)의 입력이 된다.
원전: docs/무한매수법.md §4~§5.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionState:
    """무한매수법 사이클의 핵심 상태 (평단은 파생)."""

    holding_qty: int
    cumulative_buy: float

    @property
    def avg_price(self) -> float:
        """평단 = 매수누적액 / 보유수량 (보유 0이면 0.0)."""
        if self.holding_qty <= 0:
            return 0.0
        return self.cumulative_buy / self.holding_qty


def apply_buy(state: PositionState, fill_price: float, fill_qty: int) -> PositionState:
    """매수 체결 반영: 보유수량·매수누적액 증가(평단은 파생 재계산)."""
    return PositionState(
        holding_qty=state.holding_qty + fill_qty,
        cumulative_buy=state.cumulative_buy + fill_price * fill_qty,
    )


def apply_sell(state: PositionState, fill_price: float, fill_qty: int) -> tuple[PositionState, float]:
    """매도 체결 반영: 보유수량·매수누적액 비례 감소. 반환 (새 상태, 실현수익).

    매수누적액은 평단×매도수량(원가)만큼 줄어 평단이 유지된다.
    실현수익 = (체결가 - 평단) × 매도수량. 매도수량이 보유수량을 넘으면 보유분까지만 매도(음수 방지).
    """
    sold = min(fill_qty, state.holding_qty)
    avg = state.avg_price
    new_qty = state.holding_qty - sold
    new_cumulative = state.cumulative_buy - avg * sold
    realized = (fill_price - avg) * sold
    return PositionState(holding_qty=new_qty, cumulative_buy=max(new_cumulative, 0.0)), realized


def is_cycle_complete(state: PositionState) -> bool:
    """보유수량이 0이면 사이클 종료(전량 청산)."""
    return state.holding_qty == 0


def next_cycle_seed(prev_cycle_no: int) -> tuple[PositionState, int]:
    """전량 청산 후 새 사이클의 시드를 반환한다: (빈 상태, 다음 사이클 번호).

    원전 §5: 지정가매도로 전량 청산되면 사이클이 끝나고 첫 매수부터 새 사이클 시작.
    회당금액(per_round_amount)은 사이클 간 이어지므로 이 함수가 다루지 않는다(서비스 책임).
    """
    return PositionState(holding_qty=0, cumulative_buy=0.0), prev_cycle_no + 1
