"""배당 파생 지표 서비스 — 점수표 산정용."""

from collections import defaultdict
from datetime import date, timedelta

from src.database.models import StockDividend
from src.database.stock_dividend_repository import StockDividendRepository

_QUARTERLY_LABEL = "QUARTERLY"


class DividendService:
    """`stock_dividends`에서 파생 지표를 계산한다.

    - 분기 배당 실시 여부 (점수표 5점)
    - 배당 연속 인상 연수 (점수표 5점)
    """

    def __init__(self, dividend_repository: StockDividendRepository) -> None:
        self._repo = dividend_repository

    def is_quarterly_dividend(self, ticker_id: int, today: date | None = None) -> bool:
        """최근 1년 내 `kind == 'QUARTERLY'` row가 1건 이상이면 분기배당."""
        base = today or date.today()
        rows = self._repo.find_by_ticker(
            ticker_id, from_date=base - timedelta(days=365), to_date=base,
        )
        return any(r.kind == _QUARTERLY_LABEL for r in rows)

    def is_quarterly_dividend_bulk(
            self, ticker_ids: list[int], today: date | None = None,
    ) -> dict[int, bool]:
        """다건 ticker에 대해 분기 배당 여부 일괄 판정. 쿼리 1회.

        결과 dict은 입력의 모든 ticker_id를 포함(데이터 없으면 False).
        """
        if not ticker_ids:
            return {}
        base = today or date.today()
        rows = self._repo.find_by_tickers(
            ticker_ids, from_date=base - timedelta(days=365), to_date=base,
        )
        flagged = {r.ticker_id for r in rows if r.kind == _QUARTERLY_LABEL}
        return {tid: tid in flagged for tid in ticker_ids}

    def consecutive_dividend_increase_years(self, ticker_id: int) -> int:
        """최근 회계연도부터 거꾸로 본 배당 연속 인상 연수.

        점수표 정의: 동결 시 연속은 인정되나 인상으로는 인정되지 않는다.
        구현: 감소가 나오는 순간 break. 인상이면 +1, 동결이면 그대로(연속 유지).
        """
        rows = self._repo.find_by_ticker(ticker_id)
        return self._calc_streak(rows)

    def consecutive_dividend_increase_years_bulk(
            self, ticker_ids: list[int],
    ) -> dict[int, int]:
        """다건 ticker에 대해 연속 인상 연수 일괄 산출. 쿼리 1회.

        결과 dict은 입력의 모든 ticker_id를 포함(데이터 없으면 0).
        """
        if not ticker_ids:
            return {}
        rows = self._repo.find_by_tickers(ticker_ids)
        grouped: dict[int, list[StockDividend]] = defaultdict(list)
        for r in rows:
            grouped[r.ticker_id].append(r)
        return {tid: self._calc_streak(grouped.get(tid, [])) for tid in ticker_ids}

    @staticmethod
    def _calc_streak(rows: list[StockDividend]) -> int:
        if not rows:
            return 0
        year_to_dps: dict[int, float] = defaultdict(float)
        for r in rows:
            year_to_dps[r.fiscal_year] += r.dps
        years_desc = sorted(year_to_dps.keys(), reverse=True)
        streak = 0
        for i in range(len(years_desc) - 1):
            cur = year_to_dps[years_desc[i]]
            prev = year_to_dps[years_desc[i + 1]]
            if cur < prev:
                break
            if cur > prev:
                streak += 1
        return streak
