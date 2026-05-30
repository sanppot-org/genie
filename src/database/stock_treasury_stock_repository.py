"""StockTreasuryStock Repository."""

from datetime import date
import logging

from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockTreasuryStock

logger = logging.getLogger(__name__)


class StockTreasuryStockRepository(BaseRepository[StockTreasuryStock, int]):
    """자사주 보유 비율 시계열 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    """

    def _get_model_class(self) -> type[StockTreasuryStock]:
        return StockTreasuryStock

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "stlm_dt")

    def find_by_ticker(
            self,
            ticker_id: int,
            from_date: date | None = None,
            to_date: date | None = None,
    ) -> list[StockTreasuryStock]:
        """종목 ID로 결산일 범위 조회 (stlm_dt 오름차순)."""
        query = self.session.query(StockTreasuryStock).filter(StockTreasuryStock.ticker_id == ticker_id)
        if from_date is not None:
            query = query.filter(StockTreasuryStock.stlm_dt >= from_date)
        if to_date is not None:
            query = query.filter(StockTreasuryStock.stlm_dt <= to_date)
        return query.order_by(StockTreasuryStock.stlm_dt.asc()).all()

    def latest_by_tickers(self, ticker_ids: list[int]) -> dict[int, tuple[int, float]]:
        """다건 ticker의 최신(stlm_dt 최대) issued_shares·treasury_ratio. 쿼리 1회.

        `DISTINCT ON (ticker_id)`로 종목별 가장 최근 결산 row만 반환.
        결과 dict은 매칭된 ticker_id만 포함(treasury row 없는 종목은 키 자체가 없음).
        """
        if not ticker_ids:
            return {}
        rows = (
            self.session.query(
                StockTreasuryStock.ticker_id,
                StockTreasuryStock.issued_shares,
                StockTreasuryStock.treasury_ratio,
            )
            .filter(StockTreasuryStock.ticker_id.in_(ticker_ids))
            .distinct(StockTreasuryStock.ticker_id)
            .order_by(StockTreasuryStock.ticker_id, StockTreasuryStock.stlm_dt.desc())
            .all()
        )
        return {row[0]: (row[1], row[2]) for row in rows}

    def bulk_upsert(self, entities: list[StockTreasuryStock]) -> None:
        """Postgres ON CONFLICT로 (ticker_id, stlm_dt) 키 일괄 UPSERT.

        동일 키 중복 entity는 마지막 값으로 dedup된 뒤 적용된다.
        """
        if not entities:
            return

        unique_map: dict[tuple[int, date], dict] = {}
        for e in entities:
            unique_map[(e.ticker_id, e.stlm_dt)] = {
                "ticker_id": e.ticker_id,
                "stlm_dt": e.stlm_dt,
                "reprt_code": e.reprt_code,
                "issued_shares": e.issued_shares,
                "treasury_shares": e.treasury_shares,
                "treasury_ratio": e.treasury_ratio,
                "rcept_no": e.rcept_no,
            }

        stmt = insert(StockTreasuryStock).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_id", "stlm_dt"],
            set_={
                "reprt_code": stmt.excluded.reprt_code,
                "issued_shares": stmt.excluded.issued_shares,
                "treasury_shares": stmt.excluded.treasury_shares,
                "treasury_ratio": stmt.excluded.treasury_ratio,
                "rcept_no": stmt.excluded.rcept_no,
            },
        )

        self.session.execute(stmt)
