"""Ticker service for business logic."""
from sqlalchemy.exc import IntegrityError

from src.api.schemas import TickerCreate
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository
from src.service.exceptions import GenieError


class TickerService:
    """Ticker 비즈니스 로직 서비스."""

    def __init__(self, repository: TickerRepository) -> None:
        """TickerService 초기화.

        Args:
            repository: TickerRepository 인스턴스
        """
        self._repo = repository

    def upsert(self, ticker_in: TickerCreate) -> Ticker:
        """Ticker 생성 또는 업데이트 (upsert).

        Args:
            ticker_in: Ticker 생성 요청 스키마

        Returns:
            생성 또는 업데이트된 Ticker
        """
        try:
            return self._repo.save(ticker_in.to_entity())
        except IntegrityError as e:
            raise GenieError.not_found(ticker_in.exchange_id) from e

    def get_all(self) -> list[Ticker]:
        """전체 ticker 조회.

        Returns:
            모든 Ticker 목록
        """
        return self._repo.find_all()

    def get_by_id(self, ticker_id: int) -> Ticker:
        """ID로 ticker 조회.

        Args:
            ticker_id: 조회할 ticker ID

        Returns:
            조회된 Ticker

        Raises:
            TickerNotFoundError: 존재하지 않는 ticker인 경우
        """
        ticker = self._repo.find_by_id(ticker_id)

        if ticker:
            return ticker

        raise GenieError.not_found(ticker_id)

    def delete(self, ticker_id: int) -> None:
        """ticker 삭제 (없으면 무시).

        Args:
            ticker_id: 삭제할 ticker ID
        """
        self._repo.delete_by_id(ticker_id)
