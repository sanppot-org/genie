"""StockDividend Repository."""

from datetime import date
import logging

from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockDividend

logger = logging.getLogger(__name__)


class StockDividendRepository(BaseRepository[StockDividend, int]):
    """배당 이력 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    """

    def _get_model_class(self) -> type[StockDividend]:
        return StockDividend

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "record_date", "kind")

    def find_by_ticker(
            self,
            ticker_id: int,
            from_date: date | None = None,
            to_date: date | None = None,
    ) -> list[StockDividend]:
        """종목 ID로 기준일 범위 조회 (record_date 오름차순)."""
        query = self.session.query(StockDividend).filter(StockDividend.ticker_id == ticker_id)
        if from_date is not None:
            query = query.filter(StockDividend.record_date >= from_date)
        if to_date is not None:
            query = query.filter(StockDividend.record_date <= to_date)
        return query.order_by(StockDividend.record_date.asc()).all()

    def bulk_upsert(self, entities: list[StockDividend]) -> None:
        """Postgres ON CONFLICT로 (ticker_id, record_date, kind) 키 일괄 UPSERT.

        동일 키 중복 entity는 마지막 값으로 dedup된 뒤 적용된다.
        """
        if not entities:
            return

        unique_map: dict[tuple[int, date, str], dict] = {}
        for e in entities:
            unique_map[(e.ticker_id, e.record_date, e.kind)] = {
                "ticker_id": e.ticker_id,
                "record_date": e.record_date,
                "pay_date": e.pay_date,
                "dps": e.dps,
                "kind": e.kind,
                "fiscal_year": e.fiscal_year,
            }

        stmt = insert(StockDividend).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_id", "record_date", "kind"],
            set_={
                "pay_date": stmt.excluded.pay_date,
                "dps": stmt.excluded.dps,
                "fiscal_year": stmt.excluded.fiscal_year,
            },
        )

        self.session.execute(stmt)
        self.session.commit()
