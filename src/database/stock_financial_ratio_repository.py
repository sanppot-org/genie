"""StockFinancialRatio Repository."""

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockFinancialRatio

logger = logging.getLogger(__name__)

# UPSERT 시 갱신할 수치 컬럼 (실적 정정 반영).
_VALUE_COLUMNS = (
    "roe", "debt_ratio", "reserve_rate", "revenue_growth",
    "op_growth", "net_growth", "eps", "bps", "sps",
)


class StockFinancialRatioRepository(BaseRepository[StockFinancialRatio, int]):
    """결산기별 재무비율 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    """

    def _get_model_class(self) -> type[StockFinancialRatio]:
        return StockFinancialRatio

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "stac_yymm")

    def find_by_ticker(self, ticker_id: int) -> list[StockFinancialRatio]:
        """종목 ID 시계열 조회 (stac_yymm 오름차순)."""
        return (
            self.session.query(StockFinancialRatio)
            .filter(StockFinancialRatio.ticker_id == ticker_id)
            .order_by(StockFinancialRatio.stac_yymm.asc())
            .all()
        )

    def latest_stac_yymm_by_ticker(self) -> dict[int, str]:
        """종목ID → 최신 stac_yymm 매핑 (증분 가드용)."""
        rows = (
            self.session.query(
                StockFinancialRatio.ticker_id,
                func.max(StockFinancialRatio.stac_yymm),
            )
            .group_by(StockFinancialRatio.ticker_id)
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def find_latest_roe_by_tickers(self, ticker_ids: list[int]) -> dict[int, float | None]:
        """다건 ticker의 최신 **결산연도(12월)** ROE. 쿼리 1회.

        KIS 연간 응답엔 결산연도 행(...12) 외에 최근 분기/TTM 잠정 행(예: 202603)이
        섞여 온다. 그대로 max(stac_yymm)를 잡으면 잠정 ROE(삼성 19% 등)가 잡혀
        실제 연간 ROE(10.85%)와 어긋난다 → `...12`(12월 결산)로 필터해 최신 회계연도만.
        대다수 KRX 종목이 12월 결산이며, 비-12월 결산 소수 종목은 키 없음(ROE 미표시).

        `DISTINCT ON (ticker_id)`로 종목별 가장 최근 결산 row만 반환.
        결과 dict은 매칭된 ticker_id만 포함. 해당 row의 roe가 NULL이면 값은 None.
        """
        if not ticker_ids:
            return {}
        rows = (
            self.session.query(
                StockFinancialRatio.ticker_id,
                StockFinancialRatio.roe,
            )
            .filter(StockFinancialRatio.ticker_id.in_(ticker_ids))
            .filter(StockFinancialRatio.stac_yymm.like("%12"))
            .distinct(StockFinancialRatio.ticker_id)
            .order_by(StockFinancialRatio.ticker_id, StockFinancialRatio.stac_yymm.desc())
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def bulk_upsert(self, entities: list[StockFinancialRatio]) -> None:
        """Postgres ON CONFLICT로 (ticker_id, stac_yymm) 키 일괄 UPSERT.

        동일 키 중복 entity는 마지막 값으로 dedup된 뒤 적용된다. 충돌 시 수치 컬럼 갱신(실적 정정).
        """
        if not entities:
            return

        unique_map: dict[tuple[int, str], dict] = {}
        for e in entities:
            unique_map[(e.ticker_id, e.stac_yymm)] = {
                "ticker_id": e.ticker_id,
                "stac_yymm": e.stac_yymm,
                **{col: getattr(e, col) for col in _VALUE_COLUMNS},
            }

        stmt = insert(StockFinancialRatio).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_id", "stac_yymm"],
            set_={col: getattr(stmt.excluded, col) for col in _VALUE_COLUMNS},
        )

        self.session.execute(stmt)
