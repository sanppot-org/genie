"""손익계산서 읽기 서비스 — ticker 코드 → 결산기별 시계열.

저장은 KIS 원본(분기=누적)이며, 표시용 가공은 이 레이어에서 파생한다:
- ANNUAL: 결산월(최빈월) 행만 채택 → 선두 미마감 분기 행(예: 202603) 제거.
- QUARTER + single: 누적값을 단일분기로 환산. 회계연도 경계는 결산월 메타 없이도
  '누적 매출 리셋(감소)' 지점으로 감지 → 3월 결산 등 비12월 결산도 대응. 그룹 첫 기는 누적=단일.
"""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from src.database.models import Ticker
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.database.ticker_repository import TickerRepository
from src.providers.kis_income_statement_client import PERIOD_ANNUAL, PERIOD_QUARTER
from src.service.exceptions import ExceptionCode, GenieError

_VALUE_FIELDS = ("sale_account", "sale_cost", "sale_totl_prfi", "bsop_prti", "op_prfi", "thtr_ntin")


@dataclass(frozen=True)
class IncomeStatementPointData:
    """결산기별 손익계산서 1건 (가공 후)."""

    stac_yymm: str
    sale_account: Decimal | None
    sale_cost: Decimal | None
    sale_totl_prfi: Decimal | None
    bsop_prti: Decimal | None
    op_prfi: Decimal | None
    thtr_ntin: Decimal | None


class IncomeStatementService:
    """KR 주식 손익계산서 시계열 조회 (쓰기는 `IncomeStatementSyncService`)."""

    def __init__(
            self,
            ticker_repository: TickerRepository,
            income_statement_repository: StockIncomeStatementRepository,
    ) -> None:
        self._tickers = ticker_repository
        self._income = income_statement_repository

    def get_time_series(
            self,
            ticker_code: str,
            period_type: str,
            single_quarter: bool = False,
    ) -> tuple[Ticker, list[IncomeStatementPointData]]:
        """ticker 코드로 종목 + 손익계산서 시계열 반환. 종목 미발견 시 404."""
        ticker = self._tickers.find_by_ticker(ticker_code)
        if ticker is None:
            raise GenieError(code=ExceptionCode.NOT_FOUND, id=ticker_code)

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

        return ticker, points


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
                **{f: _sub(getattr(cur, f), getattr(prev, f)) for f in _VALUE_FIELDS},
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
