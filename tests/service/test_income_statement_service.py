"""IncomeStatementService 단위 테스트 — 연간 선두행 필터 + 분기 단일환산."""

from decimal import Decimal
from unittest.mock import MagicMock

from src.database.models import StockIncomeStatement
from src.providers.kis_income_statement_client import PERIOD_ANNUAL, PERIOD_QUARTER
from src.service.income_statement_service import IncomeStatementService


def _row(stac_yymm: str, sale: str, period_type: str) -> StockIncomeStatement:
    return StockIncomeStatement(
        ticker_id=1,
        period_type=period_type,
        stac_yymm=stac_yymm,
        sale_account=Decimal(sale),
        bsop_prti=Decimal(sale),  # 환산 검증은 sale_account만으로 충분, 동일값 사용
        thtr_ntin=Decimal(sale),
    )


def _service(rows: list[StockIncomeStatement]) -> IncomeStatementService:
    ticker_repo = MagicMock()
    ticker_repo.find_by_ticker.return_value = MagicMock(id=1, ticker="005930", name="삼성전자")
    income_repo = MagicMock()
    income_repo.find_by_ticker.return_value = rows
    return IncomeStatementService(ticker_repo, income_repo)


def test_annual_drops_leading_non_fiscal_month_row() -> None:
    """연간 시리즈에서 결산월(최빈월=12)과 다른 선두 행(202603)은 제거."""
    rows = [
        _row("202312", "2589355", PERIOD_ANNUAL),
        _row("202412", "3008709", PERIOD_ANNUAL),
        _row("202512", "3336059", PERIOD_ANNUAL),
        _row("202603", "1338734", PERIOD_ANNUAL),  # 미마감 분기 → 제거 대상
    ]
    _, points = _service(rows).get_time_series("005930", PERIOD_ANNUAL)

    assert [p.stac_yymm for p in points] == ["202312", "202412", "202512"]


def test_quarter_single_derivation_dec_fiscal() -> None:
    """12월 결산: 누적(YTD) → 단일분기 차감, 그룹 첫 기는 누적, 연 경계 리셋 감지."""
    rows = [
        _row("202503", "791405", PERIOD_QUARTER),
        _row("202506", "1537068", PERIOD_QUARTER),
        _row("202509", "2397686", PERIOD_QUARTER),
        _row("202512", "3336059", PERIOD_QUARTER),
        _row("202603", "719156", PERIOD_QUARTER),  # 새 회계연도 Q1 (리셋)
    ]
    _, points = _service(rows).get_time_series("005930", PERIOD_QUARTER, single_quarter=True)

    got = {p.stac_yymm: p.sale_account for p in points}
    assert got["202503"] == Decimal("791405")             # 그룹 첫 기 = 누적
    assert got["202506"] == Decimal("745663")             # 1537068-791405
    assert got["202509"] == Decimal("860618")             # 2397686-1537068
    assert got["202512"] == Decimal("938373")             # 3336059-2397686
    assert got["202603"] == Decimal("719156")             # 리셋 → 누적


def test_quarter_single_derivation_march_fiscal() -> None:
    """3월 결산(비12월): 결산월 메타 없이 누적 감소로 회계연도 경계 감지."""
    rows = [
        _row("202406", "100", PERIOD_QUARTER),  # FY Q1 누적
        _row("202409", "250", PERIOD_QUARTER),
        _row("202412", "400", PERIOD_QUARTER),
        _row("202503", "600", PERIOD_QUARTER),  # FY 마지막 누적
        _row("202506", "120", PERIOD_QUARTER),  # 새 FY Q1 (리셋: 120 < 600)
    ]
    _, points = _service(rows).get_time_series("005930", PERIOD_QUARTER, single_quarter=True)

    got = {p.stac_yymm: p.sale_account for p in points}
    assert got["202406"] == Decimal("100")
    assert got["202409"] == Decimal("150")
    assert got["202412"] == Decimal("150")
    assert got["202503"] == Decimal("200")
    assert got["202506"] == Decimal("120")  # 리셋 → 누적


def test_quarter_raw_when_single_false() -> None:
    """single=False면 누적 원본 그대로 반환."""
    rows = [
        _row("202503", "791405", PERIOD_QUARTER),
        _row("202506", "1537068", PERIOD_QUARTER),
    ]
    _, points = _service(rows).get_time_series("005930", PERIOD_QUARTER, single_quarter=False)

    assert [p.sale_account for p in points] == [Decimal("791405"), Decimal("1537068")]
