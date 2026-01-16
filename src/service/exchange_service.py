"""Exchange 비즈니스 로직 서비스."""

from src.api.schemas import ExchangeCreate, ExchangeUpdate
from src.database.exchange_repository import ExchangeRepository
from src.database.models import Exchange
from src.service.exceptions import GenieError


class ExchangeService:
    """Exchange 비즈니스 로직 서비스."""

    def __init__(self, repository: ExchangeRepository) -> None:
        """ExchangeService 초기화.

        Args:
            repository: ExchangeRepository 인스턴스
        """
        self._repo = repository

    def create(self, exchange_in: ExchangeCreate) -> Exchange:
        """Exchange 생성.

        Args:
            exchange_in: Exchange 생성 요청 스키마

        Returns:
            생성된 Exchange

        Raises:
            GenieError: 이미 존재하는 name인 경우
        """
        if self._repo.find_by_name(exchange_in.name):
            raise GenieError.already_exists(f"Exchange name '{exchange_in.name}'")
        return self._repo.save(exchange_in.to_entity())

    def update(self, exchange_id: int, exchange_in: ExchangeUpdate) -> Exchange:
        """Exchange 수정.

        Args:
            exchange_id: 수정할 exchange ID
            exchange_in: Exchange 수정 요청 스키마

        Returns:
            수정된 Exchange

        Raises:
            GenieError: 존재하지 않는 exchange인 경우
        """
        exchange = self._repo.find_by_id(exchange_id)
        if not exchange:
            raise GenieError.not_found(exchange_id)

        if exchange_in.name is not None:
            exchange.name = exchange_in.name
        if exchange_in.timezone is not None:
            exchange.timezone = exchange_in.timezone

        return self._repo.save(exchange)

    def get_all(self) -> list[Exchange]:
        """전체 exchange 조회.

        Returns:
            모든 Exchange 목록
        """
        return self._repo.find_all()

    def get_by_id(self, exchange_id: int) -> Exchange:
        """ID로 exchange 조회.

        Args:
            exchange_id: 조회할 exchange ID

        Returns:
            조회된 Exchange

        Raises:
            GenieError: 존재하지 않는 exchange인 경우
        """
        exchange = self._repo.find_by_id(exchange_id)

        if exchange:
            return exchange

        raise GenieError.not_found(exchange_id)

    def delete(self, exchange_id: int) -> None:
        """exchange 삭제 (없으면 무시).

        Args:
            exchange_id: 삭제할 exchange ID
        """
        self._repo.delete_by_id(exchange_id)
