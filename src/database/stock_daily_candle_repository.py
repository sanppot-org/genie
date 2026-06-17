"""StockDailyCandle Repository."""

from collections.abc import Mapping
from datetime import date, timedelta
import logging

from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import insert

from src.database.base_repository import BaseRepository
from src.database.models import StockDailyCandle

logger = logging.getLogger(__name__)

# 분할/병합 감지: 직전 거래일 대비 raw 종가 비율 밴드. KR 일일 가격제한 ±30%라
# 0.6배 미만 급락(분할·권리락·감자)·1.7배 초과 급등(병합)은 코퍼레이트 액션 신호.
_SPLIT_RATIO_LOW = 0.6
_SPLIT_RATIO_HIGH = 1.7


class StockDailyCandleRepository(BaseRepository[StockDailyCandle, int]):
    """KR 주식 일자별 OHLCV 리포지토리.

    대량 적재는 `bulk_upsert()` 사용 — Postgres ON CONFLICT 한 쿼리.
    `save()`는 BaseRepository 기본 구현 그대로 사용.
    """

    def _get_model_class(self) -> type[StockDailyCandle]:
        return StockDailyCandle

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("date", "ticker_id")

    def find_by_ticker(
            self,
            ticker_id: int,
            from_date: date | None = None,
            to_date: date | None = None,
    ) -> list[StockDailyCandle]:
        """종목 ID로 일자 범위 조회 (date 오름차순)."""
        query = self.session.query(StockDailyCandle).filter(StockDailyCandle.ticker_id == ticker_id)
        if from_date is not None:
            query = query.filter(StockDailyCandle.date >= from_date)
        if to_date is not None:
            query = query.filter(StockDailyCandle.date <= to_date)
        return query.order_by(StockDailyCandle.date.asc()).all()

    def find_by_date(self, target_date: date) -> list[StockDailyCandle]:
        """특정 일자 전 종목 스냅샷."""
        return (
            self.session.query(StockDailyCandle)
            .filter(StockDailyCandle.date == target_date)
            .all()
        )

    def bulk_upsert(self, entities: list[StockDailyCandle]) -> None:
        """Postgres ON CONFLICT로 (date, ticker_id) 키 일괄 UPSERT.

        동일 (date, ticker_id) 중복 entity는 마지막 값으로 dedup된 뒤 적용된다.
        """
        if not entities:
            return

        unique_map: dict[tuple[date, int], dict] = {}
        for e in entities:
            unique_map[(e.date, e.ticker_id)] = {
                "date": e.date,
                "ticker_id": e.ticker_id,
                "open": e.open,
                "high": e.high,
                "low": e.low,
                "close": e.close,
                "volume": e.volume,
                "trade_value": e.trade_value,
            }

        stmt = insert(StockDailyCandle).values(list(unique_map.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["date", "ticker_id"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "trade_value": stmt.excluded.trade_value,
            },
        )

        self.session.execute(stmt)

    def update_adjusted_from_rows(
        self,
        rows: list[StockDailyCandle],
        adjusted_by_date: Mapping[date, tuple[float, float, float, float, int | None]],
    ) -> int:
        """이미 로드된 row 리스트에 수정주가 매핑을 메모리에서 적용.

        세션에 attach된 ORM row의 adj_*만 세팅(원주가 불변). 매핑에 없는 날짜는 건너뜀.
        대량 백필 시 `date.in_(수천)` 재조회를 피하려 호출자가 로드한 row를 그대로 받는다.
        반환: 매칭되어 갱신된 row 수.
        """
        if not adjusted_by_date:
            return 0
        updated = 0
        for row in rows:
            value = adjusted_by_date.get(row.date)
            if value is None:
                continue
            o, h, low_, c, v = value
            row.adj_open = o
            row.adj_high = h
            row.adj_low = low_
            row.adj_close = c
            row.adj_volume = v
            updated += 1
        return updated

    def update_adjusted(
        self, ticker_id: int, adjusted_by_date: Mapping[date, tuple[float, float, float, float, int | None]]
    ) -> int:
        """종목의 기존 row를 로드해 adj_* 컬럼만 UPDATE (편의 메서드).

        원주가(open~close)는 KRX 원본으로 불변 보존. DB에 없는 날짜는 무시(fabricate 안 함).
        반환: 실제 갱신된 row 수.
        """
        if not adjusted_by_date:
            return 0
        rows = self.find_by_ticker(ticker_id)
        return self.update_adjusted_from_rows(rows, adjusted_by_date)

    def ticker_ids_with_adjusted(self) -> set[int]:
        """adj_close가 1건이라도 채워진 ticker_id 집합 (백필 재개용 skip 판정, 1쿼리)."""
        rows = (
            self.session.query(StockDailyCandle.ticker_id)
            .filter(StockDailyCandle.adj_close.isnot(None))
            .distinct()
            .all()
        )
        return {r[0] for r in rows}

    def find_split_candidate_ticker_ids(
        self,
        since: date,
        low: float = _SPLIT_RATIO_LOW,
        high: float = _SPLIT_RATIO_HIGH,
    ) -> set[int]:
        """since 이후 raw 종가가 직전 거래일 대비 밴드 밖으로 급변한 ticker_id 집합.

        분할·병합·권리락·감자 등 코퍼레이트 액션 후보(네이버 수정주가 소급 변경 대상).
        LAG로 종목별 직전 거래일 종가를 구하고, 경계일의 직전값이 윈도우 밖이 되지 않도록
        스캔 범위를 since보다 buffer만큼 앞에서 시작한다. 비교는 division 없이 곱셈으로.
        raw close 기준(adj는 back-adjust돼 절벽이 이미 제거됨 → 감지 불가).
        """
        scan_from = since - timedelta(days=10)
        prev_close = func.lag(StockDailyCandle.close).over(
            partition_by=StockDailyCandle.ticker_id,
            order_by=StockDailyCandle.date,
        ).label("prev_close")
        windowed = (
            self.session.query(
                StockDailyCandle.ticker_id.label("ticker_id"),
                StockDailyCandle.date.label("date"),
                StockDailyCandle.close.label("close"),
                prev_close,
            )
            .filter(StockDailyCandle.date >= scan_from)
            .subquery()
        )
        rows = (
            self.session.query(windowed.c.ticker_id)
            .filter(
                windowed.c.date >= since,
                windowed.c.prev_close.isnot(None),
                windowed.c.prev_close > 0,
                windowed.c.close > 0,
                or_(
                    windowed.c.close < low * windowed.c.prev_close,
                    windowed.c.close > high * windowed.c.prev_close,
                ),
            )
            .distinct()
            .all()
        )
        return {r[0] for r in rows}
