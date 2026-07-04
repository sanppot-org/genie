"""손익계산서 읽기 서비스 — ticker 코드 → 결산기별 시계열.

저장은 KIS 원본(분기=누적)이며, 표시용 가공은 이 레이어에서 파생한다:
- ANNUAL: 결산월(최빈월) 행만 채택 → 선두 미마감 분기 행(예: 202603) 제거.
- QUARTER + single: 누적값을 단일분기로 환산. 회계연도 경계는 결산월 메타 없이도
  '누적 매출 리셋(감소)' 지점으로 감지 → 3월 결산 등 비12월 결산도 대응. 그룹 첫 기는 누적=단일.
"""

from bisect import bisect_right
import calendar
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
import logging

from src.database.models import StockDailyCandle, StockFundamental, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.database.ticker_repository import TickerRepository
from src.providers.kis_estimate_client import KisEstimateClient
from src.providers.kis_income_statement_client import PERIOD_ANNUAL, PERIOD_QUARTER
from src.service.exceptions import ExceptionCode, GenieError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncomeStatementPointData:
    """결산기별 손익계산서 1건 (가공 후). is_estimate=True는 컨센서스 추정(2026E 등)."""

    stac_yymm: str
    sale_account: Decimal | None
    sale_cost: Decimal | None
    sale_totl_prfi: Decimal | None
    bsop_prti: Decimal | None
    op_prfi: Decimal | None
    thtr_ntin: Decimal | None
    eps: float | None = None
    per: float | None = None
    dps: float | None = None
    div: float | None = None
    bps: float | None = None  # 주당순자산 (액면분할 보정 적용, 현재 API 미노출 — 데이터 계층 보정)
    price: float | None = None
    is_estimate: bool = False


class IncomeStatementService:
    """KR 주식 손익계산서 시계열 조회 (쓰기는 `IncomeStatementSyncService`)."""

    def __init__(
            self,
            ticker_repository: TickerRepository,
            income_statement_repository: StockIncomeStatementRepository,
            fundamental_repository: StockFundamentalRepository,
            daily_candle_repository: StockDailyCandleRepository,
            estimate_client: KisEstimateClient | None = None,
    ) -> None:
        self._tickers = ticker_repository
        self._income = income_statement_repository
        self._fundamentals = fundamental_repository
        self._candles = daily_candle_repository
        self._estimates = estimate_client

    def get_time_series(
            self,
            ticker_code: str,
            period_type: str,
            single_quarter: bool = False,
    ) -> tuple[Ticker, list[IncomeStatementPointData]]:
        """ticker 코드로 종목 + 확정 손익계산서 시계열 반환(예상행 제외). 종목 미발견 시 404.

        예상(컨센서스 추정)행은 KIS 라이브 조회가 필요해 응답을 지연시킬 수 있으므로 이 확정 시계열과
        분리한다 — `get_annual_estimates`가 별도로 제공하고, 프론트가 병렬 조회해 병합한다.
        """
        ticker = self._resolve_ticker(ticker_code)
        points = self._confirmed_series(ticker, period_type, single_quarter)
        return ticker, points

    def get_annual_estimates(self, ticker_code: str) -> tuple[Ticker, list[IncomeStatementPointData]]:
        """종목 + 연간 컨센서스 추정행만 반환(확정행 제외). 종목 미발견 시 404.

        표시용 best-effort — estimate client 미주입/조회 실패/미커버 종목이면 빈 리스트. 추정치는
        연간만 존재하므로 항상 연간 확정 시계열을 기준(base_eps/base_ni/latest_close 도출)으로 삼는다.
        """
        ticker = self._resolve_ticker(ticker_code)
        points = self._confirmed_series(ticker, PERIOD_ANNUAL, single_quarter=False)
        candles = self._candles.find_by_ticker(ticker.id)
        latest_close = (
            float(candles[-1].adj_close if candles[-1].adj_close is not None else candles[-1].close)
            if candles else None
        )
        # 최근 확정 행 중 eps·net_income 모두 non-null인 가장 최근 행을 base로 사용.
        base_eps: float | None = None
        base_ni: float | None = None
        for p in reversed(points):
            if not p.is_estimate and p.eps is not None and p.thtr_ntin is not None:
                base_eps = p.eps
                base_ni = float(p.thtr_ntin)
                break
        estimates = self._build_estimates(points, ticker.ticker, latest_close, base_eps, base_ni)
        return ticker, estimates

    def _resolve_ticker(self, ticker_code: str) -> Ticker:
        ticker = self._tickers.find_by_ticker(ticker_code)
        if ticker is None:
            raise GenieError(code=ExceptionCode.NOT_FOUND, id=ticker_code)
        return ticker

    def _confirmed_series(
            self,
            ticker: Ticker,
            period_type: str,
            single_quarter: bool,
    ) -> list[IncomeStatementPointData]:
        """확정 손익계산서 시계열(예상행 제외)을 DB에서 조립·가공. 라이브 KIS 호출 없음."""
        rows = self._income.find_by_ticker(ticker.id, period_type)
        points = [
            IncomeStatementPointData(
                stac_yymm=r.stac_yymm,
                sale_account=r.sale_account,
                sale_cost=r.sale_cost,
                sale_totl_prfi=r.sale_totl_prfi,
                bsop_prti=r.bsop_prti,
                op_prfi=r.op_prfi,
                thtr_ntin=r.thtr_ntin,
            )
            for r in rows
        ]

        if period_type == PERIOD_ANNUAL:
            points = _keep_fiscal_year_rows(points)
        elif period_type == PERIOD_QUARTER and single_quarter:
            points = _to_single_quarter(points)

        funds = self._fundamentals.find_by_ticker(ticker.id)
        points = _enrich_with_fundamentals(points, funds)
        candles = self._candles.find_by_ticker(ticker.id)
        points = _enrich_with_price(points, candles)
        # 액면분할 보정: 주당지표(eps·dps)를 수정주가 분할계수로 환산해 분할 절벽 제거.
        # 추정행 도출 전에 수행 → base_eps가 보정값(최신은 factor≈1)으로 일관.
        points = _adjust_per_share_for_split(points, funds, candles)
        return points

    def _build_estimates(
            self,
            points: list[IncomeStatementPointData],
            ticker_code: str,
            latest_close: float | None = None,
            base_eps: float | None = None,
            base_ni: float | None = None,
    ) -> list[IncomeStatementPointData]:
        """컨센서스 추정 기간(2026E 등) 행만 도출해 반환한다(확정행 미포함, best-effort).

        - estimate client 미주입/조회 실패/미커버 종목 → 빈 리스트(예상행 없음).
        - 위치 고정 매핑은 섹터 무관 안정 확인됨(client 참조). 금융지주는 매출 정의가
          손익계산서와 달라 cross-source 대조 불가 → 별도 검증 없이 그대로 반환한다.
        - e.eps 없는 금융지주 등은 base_eps/base_ni로 예상EPS를 도출(주식수 일정 가정):
          예상EPS = base_eps × (예상순이익 / base_ni), 예상PER = 최근종가 / 예상EPS.
        - `points`(확정 시계열)는 예상 기간 중복 제거(existing)에만 쓰이고 반환에는 포함되지 않는다.
        """
        if self._estimates is None:
            return []
        try:
            fetched = self._estimates.fetch(ticker_code)
        except Exception as e:  # noqa: BLE001 — 표시용 best-effort, 상세조회는 계속돼야 함
            logger.warning("추정실적 조회 실패 ticker=%s: %r", ticker_code, e)
            return []
        if not fetched:
            return []

        existing = {p.stac_yymm for p in points}
        result: list[IncomeStatementPointData] = []
        for est in fetched:
            if not est.is_estimate or est.stac_yymm in existing:
                continue
            # EPS 결정: est.eps 있으면 사용, 없으면 base로 도출
            if est.eps is not None:
                eps: float | None = est.eps
            elif (
                base_eps is not None
                and base_ni not in (None, 0)
                and est.net_income is not None
            ):
                eps = base_eps * (float(est.net_income) / float(base_ni))  # type: ignore[arg-type]
            else:
                eps = None
            # PER 결정: 도출된 eps 기준 forward PER, 계산 불가 시 컨센서스 per 폴백
            per: float | None = (
                (latest_close / eps)
                if (latest_close is not None and eps is not None and eps != 0)
                else est.per
            )
            result.append(IncomeStatementPointData(
                stac_yymm=est.stac_yymm,
                sale_account=est.revenue,
                sale_cost=None,
                sale_totl_prfi=None,
                bsop_prti=est.operating_profit,
                op_prfi=None,
                thtr_ntin=est.net_income,
                eps=eps,
                per=per,
                price=latest_close,
                is_estimate=True,
            ))
        return result


def _enrich_with_fundamentals(
        points: list[IncomeStatementPointData],
        funds: list[StockFundamental],
) -> list[IncomeStatementPointData]:
    """각 결산기의 결산말일 시점 스냅샷(eps/per)을 point에 부여.

    펀더멘털은 date 오름차순. 결산말일 이하 중 가장 최근 row를 bisect로 선택.
    못 찾으면 eps/per은 None 유지.
    """
    if not points or not funds:
        return points

    fund_dates = [f.date for f in funds]
    enriched: list[IncomeStatementPointData] = []
    for p in points:
        period_end = _fiscal_period_end(p.stac_yymm)
        if period_end is None:
            enriched.append(p)
            continue
        idx = bisect_right(fund_dates, period_end) - 1
        if idx < 0:
            enriched.append(p)
            continue
        f = funds[idx]
        enriched.append(replace(p, eps=f.eps, per=f.per, dps=f.dps, div=f.div, bps=f.bps))
    return enriched


def _enrich_with_price(
        points: list[IncomeStatementPointData],
        candles: list[StockDailyCandle],
) -> list[IncomeStatementPointData]:
    """각 결산기의 결산말일 시점 종가(주가)를 point에 부여.

    일봉은 date 오름차순. 결산말일 이하 중 가장 최근 종가를 bisect로 선택(휴장일 보정).
    못 찾으면 price는 None 유지. EPS/PER 결측(적자 등)과 무관하게 종가는 존재한다.
    수정주가(adj_close)가 있으면 우선 사용 — 액면분할 전 원종가가 결산기 주가/PER에
    섞여 추세가 왜곡되는 문제를 방지. adj_close 미백필 시 원종가로 폴백.
    """
    if not points or not candles:
        return points

    candle_dates = [c.date for c in candles]
    enriched: list[IncomeStatementPointData] = []
    for p in points:
        period_end = _fiscal_period_end(p.stac_yymm)
        if period_end is None:
            enriched.append(p)
            continue
        idx = bisect_right(candle_dates, period_end) - 1
        if idx < 0:
            enriched.append(p)
            continue
        c = candles[idx]
        enriched.append(replace(p, price=float(c.adj_close if c.adj_close is not None else c.close)))
    return enriched


def _adjust_per_share_for_split(
        points: list[IncomeStatementPointData],
        funds: list[StockFundamental],
        candles: list[StockDailyCandle],
) -> list[IncomeStatementPointData]:
    """주당지표(eps·dps·bps)를 액면분할 분할계수로 환산해 분할 절벽 제거.

    분할계수 = adj_close / close (수정주가/원주가). EPS·DPS·BPS는 **그 값이 보고된 시점의
    주식수 기준**이므로, factor는 반드시 **fundamental 스냅샷 날짜**의 캔들에서 구한다
    (결산말일로 따로 bisect한 가격 캔들 날짜가 아님 — 분할 경계에서 날짜가 어긋나면
    엉뚱한 분할구간 factor가 곱해질 수 있어서다). eps·dps·bps에 동일 factor를 적용하므로
    배당성향(dps/eps)·유보(eps-dps)·PBR(price/bps) 비율은 보존된다.

    절대금액(매출·영업이익·순이익)·per(비율)·div(비율)는 보정하지 않는다.
    adj_close 미백필(~2014 이전)·close≤0이면 factor=1(원값 유지). 추정행은 보정 안 함.
    """
    if not points or not funds or not candles:
        return points

    fund_dates = [f.date for f in funds]
    candle_dates = [c.date for c in candles]
    adjusted: list[IncomeStatementPointData] = []
    for p in points:
        if p.is_estimate or (p.eps is None and p.dps is None and p.bps is None):
            adjusted.append(p)
            continue
        period_end = _fiscal_period_end(p.stac_yymm)
        if period_end is None:
            adjusted.append(p)
            continue
        # EPS/DPS가 나온 fundamental 스냅샷 날짜를 먼저 찾고(=_enrich_with_fundamentals와 동일 bisect),
        # 그 날짜의 분할계수를 적용해 EPS 좌표계와 factor를 정렬한다.
        fidx = bisect_right(fund_dates, period_end) - 1
        if fidx < 0:
            adjusted.append(p)
            continue
        snap_date = funds[fidx].date
        cidx = bisect_right(candle_dates, snap_date) - 1
        if cidx < 0:
            adjusted.append(p)
            continue
        c = candles[cidx]
        if c.adj_close is None or c.close is None or c.close <= 0:
            adjusted.append(p)
            continue
        factor = c.adj_close / c.close
        adjusted.append(replace(
            p,
            eps=p.eps * factor if p.eps is not None else None,
            dps=p.dps * factor if p.dps is not None else None,
            bps=p.bps * factor if p.bps is not None else None,
        ))
    return adjusted


def _fiscal_period_end(stac_yymm: str) -> date | None:
    """stac_yymm("YYYYMM") → 해당 월의 결산말일 date. 형식 불량이면 None."""
    if len(stac_yymm) != 6 or not stac_yymm.isdigit():
        return None
    year = int(stac_yymm[:4])
    month = int(stac_yymm[4:6])
    if not (1 <= month <= 12):
        return None
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def _keep_fiscal_year_rows(points: list[IncomeStatementPointData]) -> list[IncomeStatementPointData]:
    """연간 시리즈에서 결산월(최빈월)과 일치하는 행만 — 선두 미마감 분기 행 제거."""
    if len(points) < 2:
        return points
    months = [p.stac_yymm[4:6] for p in points if len(p.stac_yymm) == 6]
    if not months:
        return points
    fiscal_month = Counter(months).most_common(1)[0][0]
    return [p for p in points if p.stac_yymm[4:6] == fiscal_month]


def _to_single_quarter(points: list[IncomeStatementPointData]) -> list[IncomeStatementPointData]:
    """누적(YTD) 분기를 단일분기로 환산.

    회계연도 그룹은 누적 매출(sale_account) 감소 지점으로 감지(결산월 메타 불필요).
    그룹 첫 기는 누적=단일. 직전 기준 차감, 한쪽이라도 None이면 해당 항목 None.

    계약: 입력은 stac_yymm 오름차순이어야 한다(repository.find_by_ticker가 보장).
    누적이 strict 증가라는 가정 하에 동작 — 분기 결측(갭)이 있으면 인접 차감이
    부정확할 수 있으나, 매출 감소 감지가 회계연도 경계를 잡아 새 그룹으로 분리한다.
    """
    if not points:
        return points

    result: list[IncomeStatementPointData] = []
    prev: IncomeStatementPointData | None = None
    for cur in points:
        if prev is None or _is_year_reset(prev, cur):
            result.append(cur)  # 그룹 첫 기: 누적 == 단일
        else:
            result.append(IncomeStatementPointData(
                stac_yymm=cur.stac_yymm,
                sale_account=_sub(cur.sale_account, prev.sale_account),
                sale_cost=_sub(cur.sale_cost, prev.sale_cost),
                sale_totl_prfi=_sub(cur.sale_totl_prfi, prev.sale_totl_prfi),
                bsop_prti=_sub(cur.bsop_prti, prev.bsop_prti),
                op_prfi=_sub(cur.op_prfi, prev.op_prfi),
                thtr_ntin=_sub(cur.thtr_ntin, prev.thtr_ntin),
            ))
        prev = cur
    return result


def _is_year_reset(prev: IncomeStatementPointData, cur: IncomeStatementPointData) -> bool:
    """누적 매출이 직전보다 줄면 새 회계연도 시작으로 간주."""
    if prev.sale_account is None or cur.sale_account is None:
        return True  # 비교 불가 → 안전하게 새 그룹(잘못된 차감 방지)
    return cur.sale_account < prev.sale_account


def _sub(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None:
        return None
    return a - b
