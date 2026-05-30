"""StockCancellationEvent Repository."""

from datetime import date
import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockCancellationEvent

logger = logging.getLogger(__name__)

# UPSERT 시 갱신할 컬럼 (정정공시 반영).
_VALUE_COLUMNS = (
    "report_nm",
    "resolution_date",
    "cancel_date",
    "common_shares",
    "preferred_shares",
    "cancel_amount",
    "acquisition_method",
)


class StockCancellationEventRepository(BaseRepository[StockCancellationEvent, int]):
    """주식소각결정 공시(자사주 소각) 이벤트 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    """

    def _get_model_class(self) -> type[StockCancellationEvent]:
        return StockCancellationEvent

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "rcept_no")

    def find_by_ticker(
            self,
            ticker_id: int,
            from_date: date | None = None,
            to_date: date | None = None,
    ) -> list[StockCancellationEvent]:
        """종목 ID로 이사회결의일 범위 조회 (resolution_date 내림차순)."""
        query = self.session.query(StockCancellationEvent).filter(
            StockCancellationEvent.ticker_id == ticker_id
        )
        if from_date is not None:
            query = query.filter(StockCancellationEvent.resolution_date >= from_date)
        if to_date is not None:
            query = query.filter(StockCancellationEvent.resolution_date <= to_date)
        return query.order_by(StockCancellationEvent.resolution_date.desc()).all()

    def cancelled_shares_by_ticker(
            self,
            ticker_ids: list[int],
            from_date: date,
            to_date: date,
    ) -> dict[int, int]:
        """다건 ticker의 기간 내 소각주식수 합계(보통주+종류주). 쿼리 1회.

        resolution_date 범위 + ticker_id IN으로 필터, ticker_id별 SUM 집계.
        NULL 주식수는 0으로 간주. 결과 dict은 매칭된 ticker_id만 포함.
        """
        if not ticker_ids:
            return {}
        total = (
            func.coalesce(StockCancellationEvent.common_shares, 0)
            + func.coalesce(StockCancellationEvent.preferred_shares, 0)
        )
        rows = (
            self.session.query(
                StockCancellationEvent.ticker_id,
                func.sum(total),
            )
            .filter(
                StockCancellationEvent.ticker_id.in_(ticker_ids),
                StockCancellationEvent.resolution_date >= from_date,
                StockCancellationEvent.resolution_date <= to_date,
            )
            .group_by(StockCancellationEvent.ticker_id)
            .all()
        )
        return {row[0]: int(row[1] or 0) for row in rows}

    def existing_rcept_nos(self, ticker_id: int) -> set[str]:
        """종목 ID로 이미 적재된 접수번호 집합 (증분 가드용)."""
        rows = (
            self.session.query(StockCancellationEvent.rcept_no)
            .filter(StockCancellationEvent.ticker_id == ticker_id)
            .all()
        )
        return {row[0] for row in rows}

    def bulk_upsert(self, entities: list[StockCancellationEvent]) -> None:
        """Postgres ON CONFLICT로 (ticker_id, rcept_no) 키 일괄 UPSERT.

        동일 키 중복 entity는 마지막 값으로 dedup된 뒤 적용된다. 충돌 시 전체 컬럼 갱신(정정공시).
        """
        if not entities:
            return

        unique_map: dict[tuple[int, str], dict] = {}
        for e in entities:
            unique_map[(e.ticker_id, e.rcept_no)] = {
                "ticker_id": e.ticker_id,
                "rcept_no": e.rcept_no,
                **{col: getattr(e, col) for col in _VALUE_COLUMNS},
            }

        stmt = insert(StockCancellationEvent).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_id", "rcept_no"],
            set_={col: getattr(stmt.excluded, col) for col in _VALUE_COLUMNS},
        )

        self.session.execute(stmt)
