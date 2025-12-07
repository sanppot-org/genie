"""Candle data repositories for database access."""

from abc import ABC
from datetime import datetime, timedelta
from typing import override

from src.database.base_repository import BaseRepository
from src.database.models import CandleDaily, CandleMinute1


class BaseCandleRepository[T](BaseRepository[T, int], ABC):
    """캔들 데이터를 위한 공통 Repository 기능

    캔들 데이터 Repository들이 공유하는 공통 메서드를 제공합니다.
    """

    def get_candles(
            self,
            ticker: str,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[T]:
        """캔들 데이터 조회

        Args:
            ticker: 티커
            start_datetime: 시작 시각 (기본값: 현재로부터 1일 전)
            end_datetime: 종료 시각 (기본값: 현재 시각)

        Returns:
            캔들 리스트 (시간 순 정렬)
        """
        if end_datetime is None:
            end_datetime = datetime.now()
        if start_datetime is None:
            start_datetime = end_datetime - timedelta(days=1)

        model_class = self._get_model_class()
        return (
            self.session.query(model_class)
            .filter(
                model_class.ticker == ticker,  # type: ignore[attr-defined, arg-type]
                model_class.timestamp >= start_datetime,  # type: ignore[attr-defined, arg-type]
                model_class.timestamp <= end_datetime,  # type: ignore[attr-defined, arg-type]
            )
            .order_by(model_class.timestamp)  # type: ignore[attr-defined, arg-type]
            .all()
        )

    def get_latest_candle(self, ticker: str) -> T | None:
        """최신 캔들 데이터 조회

        Args:
            ticker: 티커

        Returns:
            최신 캔들 또는 None
        """
        model_class = self._get_model_class()
        return (
            self.session.query(model_class)
            .filter(model_class.ticker == ticker)  # type: ignore[attr-defined, arg-type]
            .order_by(model_class.timestamp.desc())  # type: ignore[attr-defined]
            .first()
        )

    def bulk_upsert(self, entities: list[T]) -> None:
        """캔들 데이터 벌크 upsert

        PostgreSQL의 ON CONFLICT를 사용하여 한 번의 쿼리로
        여러 레코드를 삽입하거나 업데이트합니다.

        Args:
            entities: 저장할 캔들 리스트

        Example:
            >>> candles = [CandleMinute1(...), CandleMinute1(...), ...]
            >>> repository.bulk_upsert(candles)
        """
        from sqlalchemy.dialects.postgresql import insert

        if not entities:
            return

        model_class = self._get_model_class()

        # 딕셔너리 리스트로 변환 (SQLAlchemy 객체 → dict)
        values = [
            {
                "timestamp": e.timestamp,  # type: ignore[attr-defined]
                "ticker": e.ticker,  # type: ignore[attr-defined]
                "open": e.open,  # type: ignore[attr-defined]
                "high": e.high,  # type: ignore[attr-defined]
                "low": e.low,  # type: ignore[attr-defined]
                "close": e.close,  # type: ignore[attr-defined]
                "volume": e.volume,  # type: ignore[attr-defined]
            }
            for e in entities
        ]

        # INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(model_class).values(values)
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


class CandleMinute1Repository(BaseCandleRepository[CandleMinute1]):
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


class CandleDailyRepository(BaseCandleRepository[CandleDaily]):
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
