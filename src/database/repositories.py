"""Price data repository for database access."""

from datetime import datetime

from src.database.base_repository import BaseRepository
from src.database.candle_repositories import CandleDailyRepository, CandleMinute1Repository
from src.database.models import PriceData

__all__ = ["PriceRepository", "CandleDailyRepository", "CandleMinute1Repository"]


class PriceRepository(BaseRepository[PriceData, int]):
    """가격 데이터 Repository

    가격 데이터의 CRUD 작업을 담당합니다.
    """

    def _get_model_class(self) -> type[PriceData]:
        """모델 클래스 반환

        Returns:
            PriceData 클래스
        """
        return PriceData

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        """Unique constraint 필드 반환

        Returns:
            (timestamp, symbol, source)
        """
        return "timestamp", "symbol", "source"

    def get_latest_price(self, symbol: str, source: str) -> PriceData | None:
        """최신 가격 조회

        Args:
            symbol: 심볼
            source: 데이터 소스

        Returns:
            최신 PriceData 또는 None
        """
        return (
            self.session.query(PriceData)
            .filter(PriceData.symbol == symbol, PriceData.source == source)
            .order_by(PriceData.timestamp.desc())
            .first()
        )

    def get_price_history(
            self,
            symbol: str,
            start_date: datetime,
            end_date: datetime,
            source: str | None = None,
    ) -> list[PriceData]:
        """기간별 가격 이력 조회

        Args:
            symbol: 심볼
            start_date: 시작 시각
            end_date: 종료 시각
            source: 데이터 소스 (선택)

        Returns:
            PriceData 리스트 (시간 순 정렬)
        """
        query = self.session.query(PriceData).filter(
            PriceData.symbol == symbol,
            PriceData.timestamp >= start_date,
            PriceData.timestamp <= end_date,
        )

        if source:
            query = query.filter(PriceData.source == source)

        return query.order_by(PriceData.timestamp).all()
