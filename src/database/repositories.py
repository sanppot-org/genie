"""Repository pattern for database access."""

from datetime import datetime
from typing import override

from src.database.base_repository import BaseRepository
from src.database.models import CandleDaily, CandleMinute1, PriceData


class CandleMinute1Repository(BaseRepository[CandleMinute1, int]):
    """1분봉 캔들 데이터 Repository

    1분봉 캔들 데이터의 CRUD 작업을 담당합니다.
    """

    @override
    def _get_model_class(self) -> type[CandleMinute1]:
        """모델 클래스 반환

        Returns:
            CandleMinute1 클래스
        """
        return CandleMinute1

    @override
    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        """Unique constraint 필드 반환

        Returns:
            (timestamp, ticker)
        """
        return "timestamp", "ticker"

    def get_candles(
            self,
            ticker: str,
            start_date: datetime,
            end_date: datetime,
    ) -> list[CandleMinute1]:
        """1분봉 캔들 데이터 조회

        Args:
            ticker: 티커
            start_date: 시작 시각
            end_date: 종료 시각

        Returns:
            CandleMinute1 리스트 (시간 순 정렬)
        """
        return (
            self.session.query(CandleMinute1)
            .filter(
                CandleMinute1.ticker == ticker,
                CandleMinute1.timestamp >= start_date,
                CandleMinute1.timestamp <= end_date,
            )
            .order_by(CandleMinute1.timestamp)
            .all()
        )

    def get_latest_candle(self, ticker: str) -> CandleMinute1 | None:
        """최신 1분봉 캔들 데이터 조회

        Args:
            ticker: 티커

        Returns:
            최신 CandleMinute1 또는 None
        """
        return (
            self.session.query(CandleMinute1)
            .filter(CandleMinute1.ticker == ticker)
            .order_by(CandleMinute1.timestamp.desc())
            .first()
        )

    def bulk_upsert(self, entities: list[CandleMinute1]) -> None:
        """1분봉 캔들 데이터 벌크 upsert

        PostgreSQL의 ON CONFLICT를 사용하여 한 번의 쿼리로
        여러 레코드를 삽입하거나 업데이트합니다.

        Args:
            entities: 저장할 CandleMinute1 리스트

        Example:
            >>> candles = [CandleMinute1(...), CandleMinute1(...), ...]
            >>> repository.bulk_upsert(candles)
        """
        from sqlalchemy.dialects.postgresql import insert

        if not entities:
            return

        # 딕셔너리 리스트로 변환 (SQLAlchemy 객체 → dict)
        values = [
            {
                "timestamp": e.timestamp,
                "ticker": e.ticker,
                "open": e.open,
                "high": e.high,
                "low": e.low,
                "close": e.close,
                "volume": e.volume,
            }
            for e in entities
        ]

        # INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(CandleMinute1).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["timestamp", "ticker"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )

        self.session.execute(stmt)
        self.session.commit()


class CandleDailyRepository(BaseRepository[CandleDaily, int]):
    """일봉 캔들 데이터 Repository

    일봉 캔들 데이터의 CRUD 작업을 담당합니다.
    """

    @override
    def _get_model_class(self) -> type[CandleDaily]:
        """모델 클래스 반환

        Returns:
            CandleDaily 클래스
        """
        return CandleDaily

    @override
    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        """Unique constraint 필드 반환

        Returns:
            (timestamp, ticker)
        """
        return "timestamp", "ticker"

    def get_candles(
            self,
            ticker: str,
            start_date: datetime,
            end_date: datetime,
    ) -> list[CandleDaily]:
        """일봉 캔들 데이터 조회

        Args:
            ticker: 티커
            start_date: 시작 시각
            end_date: 종료 시각

        Returns:
            CandleDaily 리스트 (시간 순 정렬)
        """
        return (
            self.session.query(CandleDaily)
            .filter(
                CandleDaily.ticker == ticker,
                CandleDaily.timestamp >= start_date,
                CandleDaily.timestamp <= end_date,
            )
            .order_by(CandleDaily.timestamp)
            .all()
        )

    def get_latest_candle(self, ticker: str) -> CandleDaily | None:
        """최신 일봉 캔들 데이터 조회

        Args:
            ticker: 티커

        Returns:
            최신 CandleDaily 또는 None
        """
        return (
            self.session.query(CandleDaily)
            .filter(CandleDaily.ticker == ticker)
            .order_by(CandleDaily.timestamp.desc())
            .first()
        )

    def bulk_upsert(self, entities: list[CandleDaily]) -> None:
        """일봉 캔들 데이터 벌크 upsert

        PostgreSQL의 ON CONFLICT를 사용하여 한 번의 쿼리로
        여러 레코드를 삽입하거나 업데이트합니다.

        Args:
            entities: 저장할 CandleDaily 리스트

        Example:
            >>> candles = [CandleDaily(...), CandleDaily(...), ...]
            >>> repository.bulk_upsert(candles)
        """
        from sqlalchemy.dialects.postgresql import insert

        if not entities:
            return

        # 딕셔너리 리스트로 변환 (SQLAlchemy 객체 → dict)
        values = [
            {
                "timestamp": e.timestamp,
                "ticker": e.ticker,
                "open": e.open,
                "high": e.high,
                "low": e.low,
                "close": e.close,
                "volume": e.volume,
            }
            for e in entities
        ]

        # INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(CandleDaily).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["timestamp", "ticker"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )

        self.session.execute(stmt)
        self.session.commit()


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
