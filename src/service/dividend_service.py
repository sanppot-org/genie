"""배당 파생 지표 서비스 — 점수표 산정용."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from src.database.models import StockDailyCandle, StockDividend, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.ticker_repository import TickerRepository
from src.service.exceptions import GenieError

_QUARTERLY_LABEL = "QUARTERLY"


@dataclass(frozen=True)
class DividendHistoryPoint:
    """차트 표시용 배당 1건 (액면분할 보정 후 DPS)."""

    record_date: date
    kind: str
    dps: float
    fiscal_year: int


def _adjust_dps_for_split(
        rows: list[StockDividend],
        candles: list[StockDailyCandle],
) -> list[DividendHistoryPoint]:
    """각 배당 레코드의 record_date 시점 분할계수(adj_close/close)로 DPS를 환산.

    네이버 수정주가는 '오늘 주식수' 기준으로 back-adjust돼 있어, record_date의 factor를
    곱하면 과거 배당도 동일 주식수 좌표계로 정렬돼 분할 절벽이 사라진다
    (예: 삼성 2018-03 17,700 × 0.02 = 354 → 분할 후 354와 연속). 캔들은 date 오름차순,
    record_date 이하 가장 최근 캔들을 bisect로 선택(휴장일 보정).
    캔들/adj_close 미존재·close≤0이면 factor=1(원값 유지).
    """
    if not rows:
        return []
    candle_dates = [c.date for c in candles]
    points: list[DividendHistoryPoint] = []
    for r in rows:
        factor = 1.0
        if candle_dates:
            idx = bisect_right(candle_dates, r.record_date) - 1
            if idx >= 0:
                c = candles[idx]
                if c.adj_close is not None and c.close is not None and c.close > 0:
                    factor = c.adj_close / c.close
        points.append(DividendHistoryPoint(
            record_date=r.record_date,
            kind=r.kind,
            dps=r.dps * factor,
            fiscal_year=r.fiscal_year,
        ))
    return points


class DividendService:
    """`stock_dividends`에서 파생 지표를 계산한다.

    - 분기 배당 실시 여부 (점수표 5점)
    - 배당 연속 인상 연수 (점수표 5점)
    - 배당 지급 이력 조회 (차트 표시용)
    """

    def __init__(
            self,
            dividend_repository: StockDividendRepository,
            ticker_repository: TickerRepository,
            daily_candle_repository: StockDailyCandleRepository,
    ) -> None:
        self._repo = dividend_repository
        self._tickers = ticker_repository
        self._candles = daily_candle_repository

    def get_history(
            self,
            ticker_code: str,
            from_date: date | None = None,
            to_date: date | None = None,
    ) -> tuple[Ticker, list[DividendHistoryPoint]]:
        """ticker 코드로 종목 + 일자 범위 배당 이력 반환 (액면분할 보정 DPS). 종목 미발견 시 404."""
        ticker = self._tickers.find_by_ticker(ticker_code)
        if ticker is None:
            raise GenieError.not_found(0)
        rows = self._repo.find_by_ticker(ticker.id, from_date, to_date)
        candles = self._candles.find_by_ticker(ticker.id)
        return ticker, _adjust_dps_for_split(rows, candles)

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

    def consecutive_dividend_increase_years(
            self, ticker_id: int, today: date | None = None,
    ) -> int:
        """최근 회계연도부터 거꾸로 본 배당 연속 인상 연수.

        점수표 정의: 동결 시 연속은 인정되나 인상으로는 인정되지 않는다.
        구현: 감소가 나오는 순간 break. 인상이면 +1, 동결이면 그대로(연속 유지).
        """
        rows = self._repo.find_by_ticker(ticker_id)
        return self._calc_streak(rows, today)

    def consecutive_dividend_increase_years_bulk(
            self, ticker_ids: list[int], today: date | None = None,
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
        return {tid: self._calc_streak(grouped.get(tid, []), today) for tid in ticker_ids}

    @staticmethod
    def _calc_streak(rows: list[StockDividend], today: date | None = None) -> int:
        """진행 중인 회계연도 row는 부분합이라 비교에서 제외한다.

        한국 12월 결산 + 3월 정기 주총 + 4월 배당 공시 관행 기준 cutoff:
        - 5월 이후: 작년까지는 완료 → cutoff = year - 1
        - 4월 이전: 작년치도 아직 미마감 → cutoff = year - 2

        '연속 인상'은 현재성·연속성을 요구한다:
        - recency: 가장 최신 비교 연도가 cutoff_year(가장 최근 완료 회계연도)가 아니면
          최근 배당이 끊긴 것 → 0. (오래전 끝난 인상 행진은 인정하지 않는다)
        - 연속성: 연도가 1년씩 이어져야 한다. 배당 중단으로 연도가 단절되면 그 지점에서
          끊긴다. (dps<=0은 sync에서 적재되지 않으므로 결측 연도 = 중단으로 본다)
        동결은 연속을 끊지 않지만 인상 카운트엔 포함되지 않는다.
        """
        if not rows:
            return 0
        today = today or date.today()
        cutoff_year = today.year - 1 if today.month >= 5 else today.year - 2

        year_to_dps: dict[int, float] = defaultdict(float)
        for r in rows:
            if r.fiscal_year > cutoff_year:
                continue
            year_to_dps[r.fiscal_year] += r.dps
        years_desc = sorted(year_to_dps.keys(), reverse=True)

        # recency 앵커: 최근 완료 회계연도에 배당이 없으면 '진행 중 연속'이 아니다.
        if not years_desc or years_desc[0] != cutoff_year:
            return 0

        streak = 0
        for i in range(len(years_desc) - 1):
            # 연도 단절(배당 중단)은 연속을 끊는다.
            if years_desc[i] - years_desc[i + 1] != 1:
                break
            cur = year_to_dps[years_desc[i]]
            prev = year_to_dps[years_desc[i + 1]]
            if cur < prev:
                break
            if cur > prev:
                streak += 1
        return streak
