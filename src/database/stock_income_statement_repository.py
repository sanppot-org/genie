"""StockIncomeStatement Repository."""

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockIncomeStatement

logger = logging.getLogger(__name__)

# UPSERT 시 갱신할 금액 컬럼 (실적 정정 반영).
_VALUE_COLUMNS = ("sale_account", "sale_cost", "sale_totl_prfi", "bsop_prti", "op_prfi", "thtr_ntin")


class StockIncomeStatementRepository(BaseRepository[StockIncomeStatement, int]):
    """결산기별 손익계산서 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    """

    def _get_model_class(self) -> type[StockIncomeStatement]:
        return StockIncomeStatement

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "period_type", "stac_yymm")

    def find_by_ticker(self, ticker_id: int, period_type: str) -> list[StockIncomeStatement]:
        """종목 ID + period_type 시계열 조회 (stac_yymm 오름차순)."""
        return (
            self.session.query(StockIncomeStatement)
            .filter(
                StockIncomeStatement.ticker_id == ticker_id,
                StockIncomeStatement.period_type == period_type,
            )
            .order_by(StockIncomeStatement.stac_yymm.asc())
            .all()
        )

    def latest_stac_yymm_by_ticker(self, period_type: str) -> dict[int, str]:
        """period_type별 종목ID → 최신 stac_yymm 매핑 (증분 가드용)."""
        rows = (
            self.session.query(
                StockIncomeStatement.ticker_id,
                func.max(StockIncomeStatement.stac_yymm),
            )
            .filter(StockIncomeStatement.period_type == period_type)
            .group_by(StockIncomeStatement.ticker_id)
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def bulk_upsert(self, entities: list[StockIncomeStatement]) -> None:
        """Postgres ON CONFLICT로 (ticker_id, period_type, stac_yymm) 키 일괄 UPSERT.

        동일 키 중복 entity는 마지막 값으로 dedup된 뒤 적용된다. 충돌 시 금액 컬럼 갱신(실적 정정).
        """
        if not entities:
            return

        unique_map: dict[tuple[int, str, str], dict] = {}
        for e in entities:
            unique_map[(e.ticker_id, e.period_type, e.stac_yymm)] = {
                "ticker_id": e.ticker_id,
                "period_type": e.period_type,
                "stac_yymm": e.stac_yymm,
                **{col: getattr(e, col) for col in _VALUE_COLUMNS},
            }

        stmt = insert(StockIncomeStatement).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_id", "period_type", "stac_yymm"],
            set_={col: getattr(stmt.excluded, col) for col in _VALUE_COLUMNS},
        )

        self.session.execute(stmt)
