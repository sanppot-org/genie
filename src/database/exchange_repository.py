"""Exchange Repository for database access."""

from typing import override

from src.database.base_repository import BaseRepository
from src.database.models import Exchange


class ExchangeRepository(BaseRepository[Exchange, int]):
    """거래소 데이터 Repository

    거래소 데이터의 CRUD 작업을 담당합니다.
    """

    @override
    def _get_model_class(self) -> type[Exchange]:
        """모델 클래스 반환

        Returns:
            Exchange 클래스
        """
        return Exchange

    @override
    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        """Unique constraint 필드 반환

        Returns:
            (name,) - 거래소 이름이 unique
        """
        return ("name",)

    def find_by_name(self, name: str) -> Exchange | None:
        """이름으로 거래소 조회

        Args:
            name: 거래소 이름

        Returns:
            거래소 또는 None
        """
        return self.session.query(Exchange).filter_by(name=name).first()

    def exists(self, name: str) -> bool:
        """거래소 존재 여부 확인

        Args:
            name: 거래소 이름

        Returns:
            존재하면 True, 아니면 False
        """
        return self.find_by_name(name) is not None
