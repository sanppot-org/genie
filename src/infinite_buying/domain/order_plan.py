"""하루치 주문계획 산출 (무한매수법 v1).

포지션 상태·config·전일종가 → 그날 KIS에 걸 주문 intent 목록.
v1 범위(스펙 §10): 여유매수 없음, 정규장 주문만.
- 보유 0(사이클 시작): 첫 매수(LOC).
- 매수 가능(매수누적액+회당금액 <= 회당금액×분할수): 매수(전반=별지점½+평단, 후반=별지점 전액)[LOC]
  + 매도(쿼터매도 별지점[LOC] + 지정가매도[LIMIT]).
  할당금액은 반복리/복리 시 수익과 함께 자라므로(§4) 항상 회당금액×분할수와 같다 — 고정 config 값이 아니다.
- 회차 소진(매수 불가): 매도만 — 쿼터매도(MOC) + 지정가매도(LIMIT).
KIS 발주는 Phase 2b 어댑터, 상태 갱신은 Phase 2c 대조잡 책임. 원전: docs/무한매수법.md §4~§5.
"""

from dataclasses import dataclass
from math import floor

from src.infinite_buying.domain.position_math import PositionState
from src.infinite_buying.domain.progress import Phase, calc_t, phase_of
from src.infinite_buying.domain.separation_point import separation_point

FIRST_BUY_PRICE_RATIO = 1.15  # 첫 매수 LOC 목표가 = 전일종가 × 1.15 (진입 보장 위해 널널하게)
SEPARATION_OFFSET = 0.01      # 별지점매수 목표가는 매도와 겹치지 않게 -0.01


@dataclass(frozen=True)
class OrderIntent:
    """그날 걸 주문 1건 (도메인 표현; KIS 발주는 어댑터 책임)."""

    side: str            # buy / sell
    order_kind: str      # first_buy / separation_buy / avg_buy / quarter_sell / limit_sell
    order_division: str  # LOC / MOC / LIMIT
    target_price: float
    qty: int


def build_daily_plan(
    state: PositionState,
    per_round_amount: float,
    prev_close: float,
    division: int,
    base_gap: float,
    sell_limit_pct: float,
) -> list[OrderIntent]:
    """그날의 주문 intent 목록을 산출한다 (qty<=0 intent는 제외)."""
    if state.holding_qty == 0:
        target = prev_close * FIRST_BUY_PRICE_RATIO
        qty = floor(per_round_amount / target) if target > 0 else 0
        return _nonempty([OrderIntent("buy", "first_buy", "LOC", target, qty)])

    t = calc_t(state.cumulative_buy, per_round_amount)
    sep = separation_point(state.avg_price, t, division, base_gap)
    # 소진 판정: 유효 할당금액 = 회당금액 × 분할수 (반복리로 회당금액이 크면 할당도 그만큼 큼) ⟺ T <= 분할수-1
    affordable = state.cumulative_buy + per_round_amount <= per_round_amount * division

    intents: list[OrderIntent] = []
    if affordable:
        intents.extend(_buy_intents(state, per_round_amount, sep, phase_of(t, division)))
        intents.extend(_sell_intents(state, sep, sell_limit_pct, "LOC"))
    else:
        intents.extend(_sell_intents(state, sep, sell_limit_pct, "MOC"))
    return _nonempty(intents)


def _buy_intents(
    state: PositionState, per_round_amount: float, sep: float, phase: Phase
) -> list[OrderIntent]:
    """전반전: 별지점매수(½)+평단매수(나머지). 후반전: 별지점매수(전액). 모두 LOC."""
    sep_target = sep - SEPARATION_OFFSET
    if phase is Phase.FIRST_HALF:
        sep_qty = floor((per_round_amount / 2) / sep_target) if sep_target > 0 else 0
        avg_qty = floor(per_round_amount / state.avg_price) - sep_qty if state.avg_price > 0 else 0
        return [
            OrderIntent("buy", "separation_buy", "LOC", sep_target, sep_qty),
            OrderIntent("buy", "avg_buy", "LOC", state.avg_price, avg_qty),
        ]
    sep_qty = floor(per_round_amount / sep_target) if sep_target > 0 else 0
    return [OrderIntent("buy", "separation_buy", "LOC", sep_target, sep_qty)]


def _sell_intents(
    state: PositionState, sep: float, sell_limit_pct: float, quarter_division: str
) -> list[OrderIntent]:
    """쿼터매도(잔량25%, 별지점, 평상시 LOC/회차소진 MOC) + 지정가매도(나머지, 평단+%)."""
    quarter_qty = floor(state.holding_qty / 4)
    limit_qty = state.holding_qty - quarter_qty
    limit_target = state.avg_price * (1 + sell_limit_pct / 100)
    return [
        OrderIntent("sell", "quarter_sell", quarter_division, sep, quarter_qty),
        OrderIntent("sell", "limit_sell", "LIMIT", limit_target, limit_qty),
    ]


def _nonempty(intents: list[OrderIntent]) -> list[OrderIntent]:
    """qty>0인 intent만 남긴다."""
    return [i for i in intents if i.qty > 0]
