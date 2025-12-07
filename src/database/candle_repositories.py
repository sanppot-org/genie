"""Candle data repositories for database access."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import override

from src.database.base_repository import BaseRepository
from src.database.models import CandleDaily, CandleMinute1


class BaseCandleRepository[T](BaseRepository[T, int], ABC):
    """캔들 데이터를 위한 공통 Repository 기능

    캔들 데이터 Repository들이 공유하는 공통 메서드를 제공합니다.
    각 서브클래스는 자신의 시간 필드(timestamp vs date)에 맞게 구현해야 합니다.
    """

    @abstractmethod
    def get_candles(
            self,
            ticker: str,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[T]:
        """캔들 데이터 조회

        Args:
            ticker: 티커
            start_datetime: 시작 시각
            end_datetime: 종료 시각

        Returns:
            캔들 리스트 (시간 순 정렬)
        """
        pass

    @abstractmethod
    def get_latest_candle(self, ticker: str) -> T | None:
        """최신 캔들 데이터 조회

        Args:
            ticker: 티커

        Returns:
            최신 캔들 또는 None
        """
        pass

    @abstractmethod
    def bulk_upsert(self, entities: list[T]) -> None:
        """캔들 데이터 벌크 upsert

        Args:
            entities: 저장할 캔들 리스트
        """
        pass


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

    @override
    def get_candles(
            self,
            ticker: str,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[CandleMinute1]:
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

        return (
            self.session.query(CandleMinute1)
            .filter(
                CandleMinute1.ticker == ticker,
                CandleMinute1.timestamp >= start_datetime,
                CandleMinute1.timestamp <= end_datetime,
            )
            .order_by(CandleMinute1.timestamp)
            .all()
        )

    @override
    def get_latest_candle(self, ticker: str) -> CandleMinute1 | None:
        """최신 캔들 데이터 조회

        Args:
            ticker: 티커

        Returns:
            최신 캔들 또는 None
        """
        return (
            self.session.query(CandleMinute1)
            .filter(CandleMinute1.ticker == ticker)
            .order_by(CandleMinute1.timestamp.desc())
            .first()
        )

    @override
    def bulk_upsert(self, entities: list[CandleMinute1]) -> None:
        """캔들 데이터 벌크 upsert

        PostgreSQL의 ON CONFLICT를 사용하여 한 번의 쿼리로
        여러 레코드를 삽입하거나 업데이트합니다.

        Args:
            entities: 저장할 캔들 리스트
        """
        from sqlalchemy.dialects.postgresql import insert

        if not entities:
            return

        # 딕셔너리 리스트로 변환 (SQLAlchemy 객체 → dict)
        values = [
            {
                "timestamp": e.timestamp,
                "localtime": e.localtime,
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
                "localtime": stmt.excluded.localtime,
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )

        self.session.execute(stmt)
        self.session.commit()


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
            (date, ticker)
        """
        return "date", "ticker"

    @override
    def get_candles(
            self,
            ticker: str,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[CandleDaily]:
        """캔들 데이터 조회 (일봉은 date 필드 사용)

        Args:
            ticker: 티커
            start_datetime: 시작 시각 (날짜로 변환됨, 기본값: 현재로부터 1일 전)
            end_datetime: 종료 시각 (날짜로 변환됨, 기본값: 현재 시각)

        Returns:
            캔들 리스트 (날짜 순 정렬)
        """
        if end_datetime is None:
            end_datetime = datetime.now()
        if start_datetime is None:
            start_datetime = end_datetime - timedelta(days=1)

        start_date = start_datetime.date()
        end_date = end_datetime.date()

        return (
            self.session.query(CandleDaily)
            .filter(
                CandleDaily.ticker == ticker,
                CandleDaily.date >= start_date,
                CandleDaily.date <= end_date,
            )
            .order_by(CandleDaily.date)
            .all()
        )

    @override
    def get_latest_candle(self, ticker: str) -> CandleDaily | None:
        """최신 캔들 데이터 조회 (일봉은 date 필드 사용)

        Args:
            ticker: 티커

        Returns:
            최신 캔들 또는 None
        """
        return (
            self.session.query(CandleDaily)
            .filter(CandleDaily.ticker == ticker)
            .order_by(CandleDaily.date.desc())
            .first()
        )

    @override
    def bulk_upsert(self, entities: list[CandleDaily]) -> None:
        """캔들 데이터 벌크 upsert (일봉은 date 필드 사용)

        PostgreSQL의 ON CONFLICT를 사용하여 한 번의 쿼리로
        여러 레코드를 삽입하거나 업데이트합니다.

        Args:
            entities: 저장할 캔들 리스트
        """
        from sqlalchemy.dialects.postgresql import insert

        if not entities:
            return

        # 딕셔너리 리스트로 변환 (SQLAlchemy 객체 → dict)
        values = [
            {
                "date": e.date,
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
            index_elements=["date", "ticker"],
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
