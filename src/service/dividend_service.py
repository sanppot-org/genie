"""배당 파생 지표 서비스 — 점수표 산정용."""

from collections import defaultdict
from datetime import date, timedelta

from src.database.stock_dividend_repository import StockDividendRepository


class DividendService:
    """`stock_dividends`에서 파생 지표를 계산한다.

    - 분기 배당 실시 여부 (점수표 5점)
    - 배당 연속 인상 연수 (점수표 5점)
    """

    QUARTERLY_THRESHOLD = 3  # 최근 1년 내 배당 횟수 기준

    def __init__(self, dividend_repository: StockDividendRepository) -> None:
        self._repo = dividend_repository

    def is_quarterly_dividend(self, ticker_id: int, today: date | None = None) -> bool:
        """최근 1년 내 배당 지급 횟수가 3회 이상이면 분기 배당으로 본다.

        (분기 회사는 결산 1 + 중간 3, 또는 중간 4 패턴 → 3건 이상이면 분기로 간주.)
        """
        base = today or date.today()
        rows = self._repo.find_by_ticker(
            ticker_id, from_date=base - timedelta(days=365), to_date=base,
        )
        return len(rows) >= self.QUARTERLY_THRESHOLD

    def consecutive_dividend_increase_years(self, ticker_id: int) -> int:
        """최근 회계연도부터 거꾸로 본 배당 연속 인상 연수.

        점수표 정의: 동결 시 연속은 인정되나 인상으로는 인정되지 않는다.
        구현: 감소가 나오는 순간 break. 인상이면 +1, 동결이면 그대로(연속 유지).
        """
        rows = self._repo.find_by_ticker(ticker_id)
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
