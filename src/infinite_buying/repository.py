"""무한매수법 원장 리포지토리 (설정/포지션).

`BaseRepository.save()`는 unique 제약 기준 upsert(flush only). 커밋은 호출자 책임.
주문(InfiniteBuyingOrder) 영속화는 발주/대조 서비스가 도입되는 Phase 2에서 추가한다.
"""

from src.database.base_repository import BaseRepository
from src.database.models import InfiniteBuyingConfig, InfiniteBuyingPosition


class InfiniteBuyingConfigRepository(BaseRepository[InfiniteBuyingConfig, int]):
    """종목별 무한매수법 설정 리포지토리 (종목당 1행)."""

    def _get_model_class(self) -> type[InfiniteBuyingConfig]:
        return InfiniteBuyingConfig

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id",)

    def find_by_ticker_id(self, ticker_id: int) -> InfiniteBuyingConfig | None:
        """종목 설정 조회."""
        return (
            self.session.query(InfiniteBuyingConfig)
            .filter(InfiniteBuyingConfig.ticker_id == ticker_id)
            .first()
        )

    def find_active(self) -> list[InfiniteBuyingConfig]:
        """활성 설정 전체 조회 (발주잡 대상 종목)."""
        return (
            self.session.query(InfiniteBuyingConfig)
            .filter(InfiniteBuyingConfig.active.is_(True))
            .order_by(InfiniteBuyingConfig.ticker_id)
            .all()
        )


class InfiniteBuyingPositionRepository(BaseRepository[InfiniteBuyingPosition, int]):
    """무한매수법 사이클 상태 리포지토리 ((ticker_id, cycle_no) 유니크)."""

    def _get_model_class(self) -> type[InfiniteBuyingPosition]:
        return InfiniteBuyingPosition

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("ticker_id", "cycle_no")

    def find_active_by_ticker(self, ticker_id: int) -> InfiniteBuyingPosition | None:
        """진행 중(status=active)인 사이클 조회 (종목당 최대 1개)."""
        return (
            self.session.query(InfiniteBuyingPosition)
            .filter(
                InfiniteBuyingPosition.ticker_id == ticker_id,
                InfiniteBuyingPosition.status == "active",
            )
            .order_by(InfiniteBuyingPosition.cycle_no.desc())
            .first()
        )
