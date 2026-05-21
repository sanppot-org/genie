"""StockBuybackEvent Repository."""

from datetime import date
import logging

from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockBuybackEvent

logger = logging.getLogger(__name__)


class StockBuybackEventRepository(BaseRepository[StockBuybackEvent, int]):
    """자기주식 취득·처분 공시 이벤트 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    """

    def _get_model_class(self) -> type[StockBuybackEvent]:
        return StockBuybackEvent

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "rcept_no")

    def find_by_ticker(
            self,
            ticker_id: int,
            from_date: date | None = None,
            to_date: date | None = None,
            event_type: str | None = None,
    ) -> list[StockBuybackEvent]:
        """종목 ID로 이사회 결의일 범위 조회 (resolution_date 내림차순)."""
        query = self.session.query(StockBuybackEvent).filter(StockBuybackEvent.ticker_id == ticker_id)
        if from_date is not None:
            query = query.filter(StockBuybackEvent.resolution_date >= from_date)
        if to_date is not None:
            query = query.filter(StockBuybackEvent.resolution_date <= to_date)
        if event_type is not None:
            query = query.filter(StockBuybackEvent.event_type == event_type)
        return query.order_by(StockBuybackEvent.resolution_date.desc()).all()

    def bulk_upsert(self, entities: list[StockBuybackEvent]) -> None:
        """Postgres ON CONFLICT로 (ticker_id, rcept_no) 키 일괄 UPSERT.

        동일 키 중복 entity는 마지막 값으로 dedup된 뒤 적용된다.
        """
        if not entities:
            return

        unique_map: dict[tuple[int, str], dict] = {}
        for e in entities:
            unique_map[(e.ticker_id, e.rcept_no)] = {
                "ticker_id": e.ticker_id,
                "rcept_no": e.rcept_no,
                "event_type": e.event_type,
                "resolution_date": e.resolution_date,
                "planned_shares": e.planned_shares,
                "planned_amount": e.planned_amount,
                "period_start": e.period_start,
                "period_end": e.period_end,
                "purpose": e.purpose,
            }

        stmt = insert(StockBuybackEvent).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_id", "rcept_no"],
            set_={
                "event_type": stmt.excluded.event_type,
                "resolution_date": stmt.excluded.resolution_date,
                "planned_shares": stmt.excluded.planned_shares,
                "planned_amount": stmt.excluded.planned_amount,
                "period_start": stmt.excluded.period_start,
                "period_end": stmt.excluded.period_end,
                "purpose": stmt.excluded.purpose,
            },
        )

        self.session.execute(stmt)
