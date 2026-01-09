"""Ticker repository for database operations."""

from src.constants import AssetType
from src.database.base_repository import BaseRepository
from src.database.models import Ticker


class TickerRepository(BaseRepository[Ticker, int]):
    """Ticker 엔티티를 위한 Repository.

    기본 CRUD 외에 ticker 코드로 조회, asset_type으로 필터링 기능 제공.
    """

    def _get_model_class(self) -> type[Ticker]:
        """Get the model class for this repository."""
        return Ticker

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        """Get unique constraint field names for upsert logic."""
        return ("ticker",)

    def find_by_ticker(self, ticker: str) -> Ticker | None:
        """티커 코드로 조회.

        Args:
            ticker: 티커 코드 (예: KRW-BTC)

        Returns:
            Ticker if found, None otherwise
        """
        return self.session.query(Ticker).filter_by(ticker=ticker).first()

    def find_by_asset_type(self, asset_type: AssetType) -> list[Ticker]:
        """자산 유형으로 필터링.

        Args:
            asset_type: 자산 유형

        Returns:
            해당 자산 유형의 모든 Ticker 목록
        """
        return self.session.query(Ticker).filter_by(asset_type=asset_type.value).all()

    def exists(self, ticker: str) -> bool:
        """티커 존재 여부 확인.

        Args:
            ticker: 티커 코드

        Returns:
            존재하면 True
        """
        return self.find_by_ticker(ticker) is not None
