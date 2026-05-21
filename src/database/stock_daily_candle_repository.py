"""StockDailyCandle Repository."""

from datetime import date
import logging

from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockDailyCandle

logger = logging.getLogger(__name__)


class StockDailyCandleRepository(BaseRepository[StockDailyCandle, int]):
    """KR 주식 일자별 OHLCV 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    `save()`는 BaseRepository 기본 구현 그대로 사용.
    """

    def _get_model_class(self) -> type[StockDailyCandle]:
        return StockDailyCandle

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("date", "ticker_id")

    def find_by_ticker(
            self,
            ticker_id: int,
            from_date: date | None = None,
            to_date: date | None = None,
    ) -> list[StockDailyCandle]:
        """종목 ID로 일자 범위 조회 (date 오름차순)."""
        query = self.session.query(StockDailyCandle).filter(StockDailyCandle.ticker_id == ticker_id)
        if from_date is not None:
            query = query.filter(StockDailyCandle.date >= from_date)
        if to_date is not None:
            query = query.filter(StockDailyCandle.date <= to_date)
        return query.order_by(StockDailyCandle.date.asc()).all()

    def find_by_date(self, target_date: date) -> list[StockDailyCandle]:
        """특정 일자 전 종목 스냅샷."""
        return (
            self.session.query(StockDailyCandle)
            .filter(StockDailyCandle.date == target_date)
            .all()
        )

    def bulk_upsert(self, entities: list[StockDailyCandle]) -> None:
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
                "open": e.open,
                "high": e.high,
                "low": e.low,
                "close": e.close,
                "volume": e.volume,
                "trade_value": e.trade_value,
            }

        stmt = insert(StockDailyCandle).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["date", "ticker_id"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "trade_value": stmt.excluded.trade_value,
            },
        )

        self.session.execute(stmt)
