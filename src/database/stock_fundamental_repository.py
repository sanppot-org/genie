"""StockFundamental Repository."""

from datetime import date
import logging

from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockFundamental

logger = logging.getLogger(__name__)


class StockFundamentalRepository(BaseRepository[StockFundamental, int]):
    """펀더멘털 일자별 스냅샷 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    `save()`는 BaseRepository 기본 구현 그대로 사용.
    """

    def _get_model_class(self) -> type[StockFundamental]:
        return StockFundamental

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("date", "ticker_id")

    def find_by_ticker(
            self,
            ticker_id: int,
            from_date: date | None = None,
            to_date: date | None = None,
    ) -> list[StockFundamental]:
        """종목 ID로 일자 범위 조회 (date 오름차순)."""
        query = self.session.query(StockFundamental).filter(StockFundamental.ticker_id == ticker_id)
        if from_date is not None:
            query = query.filter(StockFundamental.date >= from_date)
        if to_date is not None:
            query = query.filter(StockFundamental.date <= to_date)
        return query.order_by(StockFundamental.date.asc()).all()

    def find_by_date(self, target_date: date) -> list[StockFundamental]:
        """특정 일자 전체 종목 스냅샷."""
        return (
            self.session.query(StockFundamental)
            .filter(StockFundamental.date == target_date)
            .all()
        )

    def bulk_upsert(self, entities: list[StockFundamental]) -> None:
        """Postgres ON CONFLICT로 (date, ticker_id) 키 일괄 UPSERT.

        동일 (date, ticker_id) 중복 entity는 마지막 값으로 dedup된 뒤 적용된다.
        """
        if not entities:
            return

        unique_map: dict[tuple[date, int], dict] = {}
        for e in entities:
            unique_map[(e.date, e.ticker_id)] = {
                "date": e.date,
                "ticker_id": e.ticker_id,
                "bps": e.bps,
                "per": e.per,
                "pbr": e.pbr,
                "eps": e.eps,
                "div": e.div,
                "dps": e.dps,
            }

        stmt = insert(StockFundamental).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["date", "ticker_id"],
            set_={
                "bps": stmt.excluded.bps,
                "per": stmt.excluded.per,
                "pbr": stmt.excluded.pbr,
                "eps": stmt.excluded.eps,
                "div": stmt.excluded.div,
                "dps": stmt.excluded.dps,
            },
        )

        self.session.execute(stmt)
        self.session.commit()
