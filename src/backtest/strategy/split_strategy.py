"""스플릿 전략 (분할 매수 전략)

자금을 N개로 분할하여 개별 포지션으로 관리하는 전략입니다.

진입 규칙:
- 분할 1: 무조건 진입
- 분할 N (N≥2): 분할 N-1의 수익률이 -5% 도달 시 진입

청산 규칙:
- 각 분할은 자신의 진입가 기준 +3% 수익 시 개별 익절
"""

from dataclasses import dataclass
from typing import Any

import backtrader as bt


@dataclass
class SplitPosition:
    """개별 분할 포지션"""

    split_number: int  # 분할 번호 (1, 2, 3...)
    entry_price: float  # 진입가
    entry_bar: int  # 진입 bar 번호
    volume: float  # 매수 수량
    take_profit_price: float  # 익절가 (entry_price * 1.03)
    trigger_price: float  # 다음 분할 트리거가 (entry_price * 0.95)
    is_closed: bool = False  # 청산 여부


class SplitStrategy(bt.Strategy):
    """스플릿 전략 (분할 매수)

    자금을 N개로 분할하여 각 분할을 독립적인 포지션으로 관리합니다.

    Params:
        split_count: 분할 수 (기본 10)
        take_profit_rate: 익절률 (기본 0.03, +3%)
        trigger_rate: 다음 진입 트리거율 (기본 0.05, -5%)

    Example:
        >>> cerebro = bt.Cerebro()
        >>> cerebro.addstrategy(SplitStrategy, split_count=10)
        >>> cerebro.broker.setcash(100_000_000)
        >>> result = cerebro.run()
    """

    params = (
        ("split_count", 10),  # 분할 수
        ("take_profit_rate", 0.03),  # 익절률 (+3%)
        ("trigger_rate", 0.05),  # 다음 진입 트리거율 (-5%)
    )

    def __init__(self) -> None:
        """전략 초기화"""
        self.dataclose = self.datas[0].close

        # 포지션 관리
        self.positions_list: list[SplitPosition] = []
        self.current_split_count = 0

        # 주문 추적
        self.pending_orders: dict[int, Any] = {}  # split_number -> order

        # 초기 자본 저장 (고정 금액 계산용)
        self.initial_cash: float = 0.0

        # 마지막 익절가 (재진입 조건용)
        self.last_exit_price: float = 0.0

        # 통계 (테스트용)
        self.total_entries = 0
        self.total_exits = 0

        # 거래 기록 (시각화용)
        self.trade_history: list[dict[str, Any]] = []

    def start(self) -> None:
        """전략 시작 시 호출 - 초기 자본 저장"""
        self.initial_cash = self.broker.get_cash()

    @property
    def active_position_count(self) -> int:
        """활성 포지션 수"""
        return sum(1 for p in self.positions_list if not p.is_closed)

    def _get_entry_amount(self) -> float:
        """회당 진입 금액 (초기 자본 기준 고정)"""
        return self.initial_cash / self.params.split_count  # type: ignore[attr-defined]

    def _get_last_active_position(self) -> SplitPosition | None:
        """마지막 활성 포지션 반환"""
        for pos in reversed(self.positions_list):
            if not pos.is_closed:
                return pos
        return None

    def _open_split(self, split_number: int) -> None:
        """분할 진입"""
        entry_price = self.dataclose[0]
        entry_amount = self._get_entry_amount()
        volume = entry_amount / entry_price

        # 포지션 정보 생성
        position = SplitPosition(
            split_number=split_number,
            entry_price=entry_price,
            entry_bar=len(self),
            volume=volume,
            take_profit_price=entry_price * (1 + self.params.take_profit_rate),  # type: ignore[attr-defined]
            trigger_price=entry_price * (1 - self.params.trigger_rate),  # type: ignore[attr-defined]
        )

        # 매수 주문
        order = self.buy(size=volume)
        self.pending_orders[split_number] = order
        self.positions_list.append(position)
        self.current_split_count += 1

        self.log(
            f"SPLIT {split_number} OPEN: price={entry_price:.2f}, "
            f"volume={volume:.4f}, tp={position.take_profit_price:.2f}, "
            f"trigger={position.trigger_price:.2f}"
        )

    def _close_split(self, position: SplitPosition) -> None:
        """분할 청산"""
        # 실제 포지션이 있을 때만 청산 (숏 방지)
        if self.position.size <= 0:
            position.is_closed = True
            return

        # 청산할 수량이 실제 포지션보다 크면 조정
        sell_size = min(position.volume, self.position.size)
        order = self.sell(size=sell_size)
        self.pending_orders[position.split_number] = order
        position.is_closed = True

        self.log(
            f"SPLIT {position.split_number} CLOSE: "
            f"entry={position.entry_price:.2f}, exit={self.dataclose[0]:.2f}"
        )

    def _reset_strategy(self) -> None:
        """전략 리셋 - 새로운 사이클 시작"""
        self.positions_list.clear()
        self.current_split_count = 0
        self.log("STRATEGY RESET: 새로운 사이클 시작")

    def log(self, txt: str, dt: Any = None) -> None:
        """로깅"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def notify_order(self, order: Any) -> None:
        """주문 상태 알림"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            trade_date = self.datas[0].datetime.date(0)
            trade_price = order.executed.price

            if order.isbuy():
                self.total_entries += 1
                self.trade_history.append({
                    "date": trade_date,
                    "price": trade_price,
                    "type": "buy",
                    "action": "롱 진입",  # 차트 호환용
                })
                self.log(f"BUY EXECUTED: price={trade_price:.2f}")
            elif order.issell():
                self.total_exits += 1
                self.last_exit_price = trade_price  # 재진입 조건용
                self.trade_history.append({
                    "date": trade_date,
                    "price": trade_price,
                    "type": "sell",
                    "action": "롱 청산",  # 차트 호환용
                })
                self.log(f"SELL EXECUTED: price={trade_price:.2f}")

        # 대기 주문 정리
        for split_num, pending_order in list(self.pending_orders.items()):
            if pending_order == order:
                del self.pending_orders[split_num]
                break

    def next(self) -> None:
        """매 bar마다 실행되는 전략 로직"""
        # 대기 중인 주문이 있으면 스킵
        if self.pending_orders:
            return

        current_price = self.dataclose[0]

        # 1. 활성 포지션이 없으면 → 조건 충족 시 재진입
        if self.active_position_count == 0:
            # 첫 진입 (익절 이력 없음)
            if self.last_exit_price == 0:
                self._reset_strategy()
                self._open_split(split_number=1)
                return
            # 익절가 대비 -5% 하락 시 재진입
            reentry_price = self.last_exit_price * (1 - self.params.trigger_rate)  # type: ignore[attr-defined]
            if current_price <= reentry_price:
                self._reset_strategy()
                self._open_split(split_number=1)
                return
            return  # 조건 미충족 시 대기

        # 2. 활성 포지션들의 익절 조건 확인
        for pos in self.positions_list:
            if not pos.is_closed and current_price >= pos.take_profit_price:
                self._close_split(pos)
                return  # 한 번에 하나씩 처리

        # 3. 다음 분할 트리거 확인
        last_active = self._get_last_active_position()
        if (
            last_active
            and self.current_split_count < self.params.split_count  # type: ignore[attr-defined]
            and current_price <= last_active.trigger_price
        ):
            self._open_split(split_number=self.current_split_count + 1)
