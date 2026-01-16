"""Candle data repositories for database access."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import override

from src.database.base_repository import BaseRepository, ReadOnlyRepository
from src.database.models import CandleDaily, CandleHour1, CandleMinute1


class ReadOnlyCandleRepository[T](ReadOnlyRepository[T, int], ABC):
    """읽기 전용 캔들 데이터 Repository 베이스 클래스.

    MATERIALIZED VIEW 기반 캔들 데이터(CandleHour1, CandleDaily)를 위한 베이스 클래스입니다.
    """

    @abstractmethod
    def get_candles(
            self,
            ticker_id: int,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[T]:
        """캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)
            start_datetime: 시작 시각
            end_datetime: 종료 시각

        Returns:
            캔들 리스트 (시간 순 정렬)
        """
        pass

    @abstractmethod
    def get_latest_candle(self, ticker_id: int) -> T | None:
        """최신 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            최신 캔들 또는 None
        """
        pass

    @abstractmethod
    def get_oldest_candle(self, ticker_id: int) -> T | None:
        """가장 오래된 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            가장 오래된 캔들 또는 None
        """
        pass


class WritableCandleRepository[T](BaseRepository[T, int], ABC):
    """읽기/쓰기 가능한 캔들 데이터 Repository 베이스 클래스.

    일반 테이블 기반 캔들 데이터(CandleMinute1)를 위한 베이스 클래스입니다.
    """

    @abstractmethod
    def get_candles(
            self,
            ticker_id: int,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[T]:
        """캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)
            start_datetime: 시작 시각
            end_datetime: 종료 시각

        Returns:
            캔들 리스트 (시간 순 정렬)
        """
        pass

    @abstractmethod
    def get_latest_candle(self, ticker_id: int) -> T | None:
        """최신 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            최신 캔들 또는 None
        """
        pass

    @abstractmethod
    def get_oldest_candle(self, ticker_id: int) -> T | None:
        """가장 오래된 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            가장 오래된 캔들 또는 None
        """
        pass


class CandleMinute1Repository(WritableCandleRepository[CandleMinute1]):
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
            (local_time, ticker_id)
        """
        return "local_time", "ticker_id"

    @override
    def get_candles(
            self,
            ticker_id: int,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[CandleMinute1]:
        """캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)
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
                CandleMinute1.ticker_id == ticker_id,
                CandleMinute1.timestamp >= start_datetime,
                CandleMinute1.timestamp <= end_datetime,
            )
            .order_by(CandleMinute1.timestamp)
            .all()
        )

    @override
    def get_latest_candle(self, ticker_id: int) -> CandleMinute1 | None:
        """최신 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            최신 캔들 또는 None
        """
        return (
            self.session.query(CandleMinute1)
            .filter(CandleMinute1.ticker_id == ticker_id)
            .order_by(CandleMinute1.timestamp.desc())
            .first()
        )

    @override
    def get_oldest_candle(self, ticker_id: int) -> CandleMinute1 | None:
        """가장 오래된 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            가장 오래된 캔들 또는 None
        """
        return (
            self.session.query(CandleMinute1)
            .filter(CandleMinute1.ticker_id == ticker_id)
            .order_by(CandleMinute1.timestamp.asc())
            .first()
        )

    def bulk_upsert(self, entities: list[CandleMinute1]) -> None:
        """캔들 데이터 벌크 upsert

        PostgreSQL의 ON CONFLICT를 사용하여 한 번의 쿼리로
        여러 레코드를 삽입하거나 업데이트합니다.

        Note:
            동일한 (local_time, ticker_id) 조합의 중복 데이터는 마지막 값만 사용됩니다.

        Args:
            entities: 저장할 캔들 리스트
        """
        from sqlalchemy.dialects.postgresql import insert

        if not entities:
            return

        # 딕셔너리로 중복 제거 (동일 키는 마지막 값으로 덮어씀)
        unique_map: dict[tuple[datetime, int], dict] = {}
        for e in entities:
            key = (e.local_time, e.ticker_id)
            unique_map[key] = {
                "local_time": e.local_time,
                "ticker_id": e.ticker_id,
                "open": e.open,
                "high": e.high,
                "low": e.low,
                "close": e.close,
                "volume": e.volume,
                "timestamp": e.timestamp,
            }

        values = list(unique_map.values())

        # INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(CandleMinute1).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["local_time", "ticker_id"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "timestamp": stmt.excluded.timestamp,
            },
        )

        self.session.execute(stmt)
        self.session.commit()


class CandleHour1Repository(ReadOnlyCandleRepository[CandleHour1]):
    """1시간봉 캔들 데이터 Repository (MATERIALIZED VIEW - 읽기 전용)

    1시간봉 캔들 데이터의 조회 작업을 담당합니다.
    MATERIALIZED VIEW이므로 쓰기 작업은 지원하지 않습니다.
    """

    @override
    def _get_model_class(self) -> type[CandleHour1]:
        """모델 클래스 반환

        Returns:
            CandleHour1 클래스
        """
        return CandleHour1

    @override
    def get_candles(
            self,
            ticker_id: int,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[CandleHour1]:
        """캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)
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
            self.session.query(CandleHour1)
            .filter(
                CandleHour1.ticker_id == ticker_id,
                CandleHour1.local_time >= start_datetime,
                CandleHour1.local_time <= end_datetime,
            )
            .order_by(CandleHour1.local_time)
            .all()
        )

    @override
    def get_latest_candle(self, ticker_id: int) -> CandleHour1 | None:
        """최신 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            최신 캔들 또는 None
        """
        return (
            self.session.query(CandleHour1)
            .filter(CandleHour1.ticker_id == ticker_id)
            .order_by(CandleHour1.local_time.desc())
            .first()
        )

    @override
    def get_oldest_candle(self, ticker_id: int) -> CandleHour1 | None:
        """가장 오래된 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            가장 오래된 캔들 또는 None
        """
        return (
            self.session.query(CandleHour1)
            .filter(CandleHour1.ticker_id == ticker_id)
            .order_by(CandleHour1.local_time.asc())
            .first()
        )


class CandleDailyRepository(ReadOnlyCandleRepository[CandleDaily]):
    """일봉 캔들 데이터 Repository (MATERIALIZED VIEW - 읽기 전용)

    일봉 캔들 데이터의 조회 작업을 담당합니다.
    MATERIALIZED VIEW이므로 쓰기 작업은 지원하지 않습니다.
    """

    @override
    def _get_model_class(self) -> type[CandleDaily]:
        """모델 클래스 반환

        Returns:
            CandleDaily 클래스
        """
        return CandleDaily

    @override
    def get_candles(
            self,
            ticker_id: int,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[CandleDaily]:
        """캔들 데이터 조회 (일봉은 date 필드 사용)

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)
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
                CandleDaily.ticker_id == ticker_id,
                CandleDaily.date >= start_date,
                CandleDaily.date <= end_date,
            )
            .order_by(CandleDaily.date)
            .all()
        )

    @override
    def get_latest_candle(self, ticker_id: int) -> CandleDaily | None:
        """최신 캔들 데이터 조회 (일봉은 date 필드 사용)

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            최신 캔들 또는 None
        """
        return (
            self.session.query(CandleDaily)
            .filter(CandleDaily.ticker_id == ticker_id)
            .order_by(CandleDaily.date.desc())
            .first()
        )

    @override
    def get_oldest_candle(self, ticker_id: int) -> CandleDaily | None:
        """가장 오래된 캔들 데이터 조회 (일봉은 date 필드 사용)

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            가장 오래된 캔들 또는 None
        """
        return (
            self.session.query(CandleDaily)
            .filter(CandleDaily.ticker_id == ticker_id)
            .order_by(CandleDaily.date.asc())
            .first()
        )
