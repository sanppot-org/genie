"""Candle data repositories for database access."""

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import InstrumentedAttribute

from src.database.base_repository import BaseRepository, HasId, ReadOnlyRepository
from src.database.models import CandleDaily, CandleHour1, CandleMinute1


class CandleQueryMixin[T](ABC):
    """캔들 조회 공통 로직 (Template Method 패턴).

    get_candles, get_latest_candle, get_oldest_candle의 쿼리 골격을 제공하며,
    서브클래스는 _get_time_column()만 오버라이드하면 됩니다.
    """

    session: Any  # ReadOnlyRepository에서 제공

    @abstractmethod
    def _get_model_class(self) -> type[T]: ...

    @abstractmethod
    def _get_time_column(self) -> InstrumentedAttribute:
        """시간 필드 컬럼 반환.

        Returns:
            SQLAlchemy 컬럼 (예: CandleMinute1.utc_time, CandleHour1.local_time, CandleDaily.date)
        """

    def _convert_boundary(self, dt: datetime) -> datetime | date:
        """경계값 변환 (기본: datetime 그대로 반환).

        CandleDailyRepository만 오버라이드하여 .date()로 변환합니다.
        """
        return dt

    def get_candles(
            self,
            ticker_id: int,
            start_datetime: datetime | None = None,
            end_datetime: datetime | None = None,
    ) -> list[T]:
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

        model = self._get_model_class()
        time_col = self._get_time_column()

        return (  # type: ignore[no-any-return]
            self.session.query(model)
            .filter(
                model.ticker_id == ticker_id,  # type: ignore[attr-defined]
                time_col >= self._convert_boundary(start_datetime),
                time_col <= self._convert_boundary(end_datetime),
            )
            .order_by(time_col)
            .all()
        )

    def get_latest_candle(self, ticker_id: int) -> T | None:
        """최신 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            최신 캔들 또는 None
        """
        model = self._get_model_class()
        return (  # type: ignore[no-any-return]
            self.session.query(model)
            .filter(model.ticker_id == ticker_id)  # type: ignore[attr-defined]
            .order_by(self._get_time_column().desc())
            .first()
        )

    def get_oldest_candle(self, ticker_id: int) -> T | None:
        """가장 오래된 캔들 데이터 조회

        Args:
            ticker_id: 티커 ID (Ticker 테이블의 PK)

        Returns:
            가장 오래된 캔들 또는 None
        """
        model = self._get_model_class()
        return (  # type: ignore[no-any-return]
            self.session.query(model)
            .filter(model.ticker_id == ticker_id)  # type: ignore[attr-defined]
            .order_by(self._get_time_column().asc())
            .first()
        )


class ReadOnlyCandleRepository[T](CandleQueryMixin[T], ReadOnlyRepository[T, int], ABC):
    """읽기 전용 캔들 데이터 Repository 베이스 클래스.

    MATERIALIZED VIEW 기반 캔들 데이터(CandleHour1, CandleDaily)를 위한 베이스 클래스입니다.
    """


class WritableCandleRepository[T: HasId](CandleQueryMixin[T], BaseRepository[T, int], ABC):
    """읽기/쓰기 가능한 캔들 데이터 Repository 베이스 클래스.

    일반 테이블 기반 캔들 데이터(CandleMinute1)를 위한 베이스 클래스입니다.
    """


class CandleMinute1Repository(WritableCandleRepository[CandleMinute1]):
    """1분봉 캔들 데이터 Repository"""

    def _get_model_class(self) -> type[CandleMinute1]:
        return CandleMinute1

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return "local_time", "ticker_id"

    def _get_time_column(self) -> InstrumentedAttribute:
        return CandleMinute1.utc_time

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
                "utc_time": e.utc_time,
            }

        values = list(unique_map.values())

        stmt = insert(CandleMinute1).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["local_time", "ticker_id"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "utc_time": stmt.excluded.utc_time,
            },
        )

        self.session.execute(stmt)
        self.session.commit()


class CandleHour1Repository(ReadOnlyCandleRepository[CandleHour1]):
    """1시간봉 캔들 데이터 Repository (MATERIALIZED VIEW - 읽기 전용)"""

    def _get_model_class(self) -> type[CandleHour1]:
        return CandleHour1

    def _get_time_column(self) -> InstrumentedAttribute:
        return CandleHour1.local_time


class CandleDailyRepository(ReadOnlyCandleRepository[CandleDaily]):
    """일봉 캔들 데이터 Repository (MATERIALIZED VIEW - 읽기 전용)"""

    def _get_model_class(self) -> type[CandleDaily]:
        return CandleDaily

    def _get_time_column(self) -> InstrumentedAttribute:
        return CandleDaily.date

    def _convert_boundary(self, dt: datetime) -> date:
        return dt.date()
