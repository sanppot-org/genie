"""KR 주식 스크리닝 — 5개 지표 점수 합산 랭킹.

점수표(`docs/종목_선정_점수표.md`) 중 자동 수집된 5개:
- PER (20점), PBR (5점), 배당수익률 (10점), 분기 배당 (5점), 연속 인상 (5점) — 합계 45점.

쿼리 4회로 전체 KR_STOCK을 메모리 join 후 정렬·페이지네이션한다.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from src.constants import AssetType
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.ticker_repository import TickerRepository
from src.service.dividend_service import DividendService

ScreeningSortBy = Literal[
    "total_score", "per", "pbr", "dividend_yield",
    "quarterly_dividend", "consecutive_years", "ticker",
]
ScreeningSortOrder = Literal["asc", "desc"]

_SORT_ATTR_MAP: dict[str, str] = {
    "total_score": "total_score",
    "per": "per",
    "pbr": "pbr",
    "dividend_yield": "dividend_yield",
    "quarterly_dividend": "quarterly_dividend",
    "consecutive_years": "consecutive_increase_years",
}


def score_per(per: float | None) -> int:
    """PER 점수: <5→20, <8→15, <10→10, ≥10→5. 적자/결측은 0."""
    if per is None or per <= 0:
        return 0
    if per < 5:
        return 20
    if per < 8:
        return 15
    if per < 10:
        return 10
    return 5


def score_pbr(pbr: float | None) -> int:
    """PBR 점수: <0.3→5, <0.6→4, <1.0→3, ≥1.0→0. 결측은 0."""
    if pbr is None or pbr <= 0:
        return 0
    if pbr < 0.3:
        return 5
    if pbr < 0.6:
        return 4
    if pbr < 1.0:
        return 3
    return 0


def score_dividend_yield(div: float | None) -> int:
    """배당수익률(%) 점수: >7→10, >5→7, >3→5, ≤3→2. 결측/0은 0."""
    if div is None or div <= 0:
        return 0
    if div > 7:
        return 10
    if div > 5:
        return 7
    if div > 3:
        return 5
    return 2


def score_quarterly_dividend(is_quarterly: bool) -> int:
    """분기 배당 실시 여부: 예→5, 아니오→0."""
    return 5 if is_quarterly else 0


def score_consecutive_increase(years: int) -> int:
    """배당 연속 인상 연수: ≥10→5, ≥5→4, ≥3→3, 그 외→0."""
    if years >= 10:
        return 5
    if years >= 5:
        return 4
    if years >= 3:
        return 3
    return 0


@dataclass(frozen=True)
class ScoreBreakdown:
    per: int
    pbr: int
    dividend_yield: int
    quarterly_dividend: int
    consecutive_increase_years: int


@dataclass(frozen=True)
class ScreeningRow:
    ticker: str
    name: str
    per: float | None
    pbr: float | None
    dividend_yield: float | None
    quarterly_dividend: bool
    consecutive_increase_years: int
    scores: ScoreBreakdown
    total_score: int


@dataclass(frozen=True)
class ScreeningFilters:
    """숫자 컬럼 임계값 필터 + 텍스트 검색.

    임계값(per/pbr/dividend_yield)은 None이면 비활성. NULL 값을 가진 종목은 해당 필터가 켜지면 제외.
    `q`는 ticker 또는 name substring (대소문자 무시). None / 빈문자열 / 공백만은 noop.
    """

    per_min: float | None = None
    per_max: float | None = None
    pbr_min: float | None = None
    pbr_max: float | None = None
    dividend_yield_min: float | None = None
    q: str | None = None

    @property
    def is_empty(self) -> bool:
        numeric_empty = all(
            getattr(self, name) is None
            for name in ("per_min", "per_max", "pbr_min", "pbr_max", "dividend_yield_min")
        )
        text_empty = not (self.q and self.q.strip())
        return numeric_empty and text_empty


@dataclass(frozen=True)
class ScreeningResult:
    target_date: date | None
    total: int
    limit: int
    offset: int
    rows: list[ScreeningRow]


def _make_sort_key(attr: str, descending: bool) -> Callable[[ScreeningRow], tuple[int, float]]:
    """비-ticker 필드용 정렬 키. NULL은 정렬 방향과 무관하게 항상 맨 뒤."""
    def key(row: ScreeningRow) -> tuple[int, float]:
        v = getattr(row, attr)
        if v is None:
            return (1, 0.0)
        primary = float(-v if descending else v)  # bool 도 -True=-1, -False=0 으로 정상 동작
        return (0, primary)
    return key


def _apply_filters(rows: list[ScreeningRow], filters: ScreeningFilters) -> list[ScreeningRow]:
    """숫자 필터 + 텍스트 검색 적용. NULL 값은 임계값이 켜진 컬럼에서 자동 제외."""
    if filters.is_empty:
        return rows

    needle = (filters.q or "").strip().lower()

    def keep(r: ScreeningRow) -> bool:
        if filters.per_min is not None and (r.per is None or r.per < filters.per_min):
            return False
        if filters.per_max is not None and (r.per is None or r.per > filters.per_max):
            return False
        if filters.pbr_min is not None and (r.pbr is None or r.pbr < filters.pbr_min):
            return False
        if filters.pbr_max is not None and (r.pbr is None or r.pbr > filters.pbr_max):
            return False
        if filters.dividend_yield_min is not None and (
                r.dividend_yield is None or r.dividend_yield < filters.dividend_yield_min):
            return False
        if needle and needle not in r.ticker.lower() and needle not in r.name.lower():
            return False
        return True

    return [r for r in rows if keep(r)]


def _apply_sort(rows: list[ScreeningRow], sort_by: ScreeningSortBy, order: ScreeningSortOrder) -> None:
    """rows를 sort_by/order 기준으로 in-place 정렬. 보조키는 항상 ticker ASC."""
    descending = order == "desc"
    if sort_by == "ticker":
        rows.sort(key=lambda r: r.ticker, reverse=descending)
        return
    attr = _SORT_ATTR_MAP[sort_by]
    rows.sort(key=lambda r: r.ticker)                  # secondary (stable sort 활용)
    rows.sort(key=_make_sort_key(attr, descending))    # primary


class ScreeningService:
    """KR_STOCK 스크리닝 점수 합산 + 정렬·페이지네이션."""

    def __init__(
            self,
            ticker_repository: TickerRepository,
            fundamental_repository: StockFundamentalRepository,
            dividend_service: DividendService,
    ) -> None:
        self._tickers = ticker_repository
        self._fundamentals = fundamental_repository
        self._dividends = dividend_service

    def score_kr_stocks(
            self,
            target_date: date | None = None,
            limit: int = 50,
            offset: int = 0,
            today: date | None = None,
            sort_by: ScreeningSortBy = "total_score",
            order: ScreeningSortOrder = "desc",
            filters: ScreeningFilters | None = None,
    ) -> ScreeningResult:
        """전체 KR_STOCK을 점수 합산해 sort_by/order 기준으로 정렬.

        기본은 total_score DESC, ticker ASC. NULL 값은 정렬 방향과 무관하게 항상 맨 뒤.
        target_date 미지정 시 `stock_fundamentals` 최신 일자 사용. 데이터 없으면 빈 결과.
        today는 분기배당 판정 기준(테스트 결정성 확보용). 기본 None → date.today().
        """
        resolved_date = target_date or self._fundamentals.find_latest_date()
        if resolved_date is None:
            return ScreeningResult(target_date=None, total=0, limit=limit, offset=offset, rows=[])

        tickers = self._tickers.find_by_asset_type(AssetType.KR_STOCK)
        if not tickers:
            return ScreeningResult(
                target_date=resolved_date, total=0, limit=limit, offset=offset, rows=[],
            )

        fundamentals = {
            f.ticker_id: f
            for f in self._fundamentals.find_by_date(resolved_date)
        }
        ticker_ids = [t.id for t in tickers]
        quarterly_map = self._dividends.is_quarterly_dividend_bulk(ticker_ids, today=today)
        streak_map = self._dividends.consecutive_dividend_increase_years_bulk(ticker_ids)

        rows: list[ScreeningRow] = []
        for t in tickers:
            f = fundamentals.get(t.id)
            per = f.per if f is not None else None
            pbr = f.pbr if f is not None else None
            div = f.div if f is not None else None
            is_q = quarterly_map.get(t.id, False)
            streak = streak_map.get(t.id, 0)

            breakdown = ScoreBreakdown(
                per=score_per(per),
                pbr=score_pbr(pbr),
                dividend_yield=score_dividend_yield(div),
                quarterly_dividend=score_quarterly_dividend(is_q),
                consecutive_increase_years=score_consecutive_increase(streak),
            )
            total = (
                breakdown.per + breakdown.pbr + breakdown.dividend_yield
                + breakdown.quarterly_dividend + breakdown.consecutive_increase_years
            )
            rows.append(ScreeningRow(
                ticker=t.ticker,
                name=t.name,
                per=per,
                pbr=pbr,
                dividend_yield=div,
                quarterly_dividend=is_q,
                consecutive_increase_years=streak,
                scores=breakdown,
                total_score=total,
            ))

        if filters is not None:
            rows = _apply_filters(rows, filters)
        _apply_sort(rows, sort_by, order)
        sliced = rows[offset:offset + limit]
        return ScreeningResult(
            target_date=resolved_date,
            total=len(rows),
            limit=limit,
            offset=offset,
            rows=sliced,
        )
