"""자사주 매입·소각 점수 판정 서비스.

`stock_buyback_events` 테이블 기반으로 점수표의
"정기적 자사주 매입·소각 (최소 연 1회 이상)" 지표를 판정한다.
"""

from datetime import date, timedelta
import logging

from src.database.stock_buyback_event_repository import StockBuybackEventRepository

logger = logging.getLogger(__name__)


class BuybackService:
    """점수표 자사주 매입·소각 판정."""

    def __init__(self, buyback_event_repository: StockBuybackEventRepository) -> None:
        self._buyback_repo = buyback_event_repository

    def is_regular_buyback(
            self,
            ticker_id: int,
            today: date,
            window_years: int = 1,
    ) -> bool:
        """`window_years` 이내 자기주식 취득결정 공시가 1건 이상이면 True.

        점수표 기준 "정기적 자사주 매입·소각 (최소 연 1회 이상)" → 7점 / 0점.
        처분은 점수 산정 대상이 아니므로 ACQUISITION만 카운트.
        """
        from_date = today - timedelta(days=365 * window_years)
        events = self._buyback_repo.find_by_ticker(
            ticker_id, from_date=from_date, to_date=today, event_type="ACQUISITION",
        )
        return len(events) > 0
