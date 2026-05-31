"""IncomeStatementService 단위 테스트 — 연간 선두행 필터 + 분기 단일환산 + EPS/PER enrich."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from src.database.models import StockDailyCandle, StockFundamental, StockIncomeStatement
from src.providers.kis_estimate_client import EstimatePointData
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


def _fund(d: date, eps: float, per: float, dps: float = 0.0, div: float = 0.0) -> StockFundamental:
    return StockFundamental(ticker_id=1, date=d, eps=eps, per=per, dps=dps, div=div)


def _candle(d: date, close: float) -> StockDailyCandle:
    return StockDailyCandle(
        ticker_id=1, date=d, open=close, high=close, low=close, close=close, volume=1,
    )


def _estimate(stac_yymm: str, is_estimate: bool, revenue: str) -> EstimatePointData:
    v = Decimal(revenue)
    return EstimatePointData(
        stac_yymm=stac_yymm,
        is_estimate=is_estimate,
        revenue=v,
        operating_profit=v,
        net_income=v,
        eps=float(v),
        per=10.0,
    )


def _service(
    rows: list[StockIncomeStatement],
    funds: list[StockFundamental] | None = None,
    candles: list[StockDailyCandle] | None = None,
    estimates: list[EstimatePointData] | None = None,
    estimate_raises: bool = False,
) -> IncomeStatementService:
    ticker_repo = MagicMock()
    ticker_repo.find_by_ticker.return_value = MagicMock(id=1, ticker="005930", name="삼성전자")
    income_repo = MagicMock()
    income_repo.find_by_ticker.return_value = rows
    fundamental_repo = MagicMock()
    fundamental_repo.find_by_ticker.return_value = funds or []
    candle_repo = MagicMock()
    candle_repo.find_by_ticker.return_value = candles or []
    estimate_client = None
    if estimates is not None or estimate_raises:
        estimate_client = MagicMock()
        if estimate_raises:
            estimate_client.fetch.side_effect = RuntimeError("KIS down")
        else:
            estimate_client.fetch.return_value = estimates
    return IncomeStatementService(
        ticker_repo, income_repo, fundamental_repo, candle_repo, estimate_client,
    )


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


def test_enrich_eps_per_snapshot_at_fiscal_period_end() -> None:
    """결산말일(2023-12-31) 이하 가장 최근 펀더멘털(2023-12-28)의 eps/per이 해당 결산기에 붙는다."""
    rows = [
        _row("202312", "100", PERIOD_ANNUAL),
        _row("202412", "200", PERIOD_ANNUAL),
    ]
    funds = [
        _fund(date(2023, 12, 28), eps=5000.0, per=12.5, dps=1444.0, div=2.5),  # 202312 결산말일 이하 최근
        _fund(date(2024, 1, 3), eps=5100.0, per=13.0),    # 202312 이후 → 무시
        _fund(date(2024, 12, 27), eps=6000.0, per=15.0, dps=1500.0, div=2.8),  # 202412 결산말일 이하 최근
    ]
    _, points = _service(rows, funds).get_time_series("005930", PERIOD_ANNUAL)

    by_yymm = {p.stac_yymm: p for p in points}
    assert by_yymm["202312"].eps == 5000.0
    assert by_yymm["202312"].per == 12.5
    assert by_yymm["202312"].dps == 1444.0
    assert by_yymm["202312"].div == 2.5
    assert by_yymm["202412"].eps == 6000.0
    assert by_yymm["202412"].per == 15.0
    assert by_yymm["202412"].dps == 1500.0
    assert by_yymm["202412"].div == 2.8


def test_enrich_none_when_no_fundamental_before_period_end() -> None:
    """가장 오래된 펀더멘털보다 앞선 결산기는 eps/per None."""
    rows = [
        _row("202012", "100", PERIOD_ANNUAL),
        _row("202312", "200", PERIOD_ANNUAL),
    ]
    funds = [_fund(date(2023, 12, 28), eps=5000.0, per=12.5)]
    _, points = _service(rows, funds).get_time_series("005930", PERIOD_ANNUAL)

    by_yymm = {p.stac_yymm: p for p in points}
    assert by_yymm["202012"].eps is None
    assert by_yymm["202012"].per is None
    assert by_yymm["202312"].eps == 5000.0


def test_enrich_price_snapshot_at_fiscal_period_end() -> None:
    """결산말일 이하 가장 최근 일봉 종가가 주가로 붙는다(휴장일은 직전 영업일 보정)."""
    rows = [
        _row("202312", "100", PERIOD_ANNUAL),
        _row("202412", "200", PERIOD_ANNUAL),
    ]
    candles = [
        _candle(date(2023, 12, 28), 70000.0),  # 202312 결산말일(12/31=휴장) 이하 최근
        _candle(date(2024, 1, 2), 71000.0),     # 202312 이후 → 무시
        _candle(date(2024, 12, 30), 53000.0),   # 202412 결산말일 이하 최근
    ]
    _, points = _service(rows, candles=candles).get_time_series("005930", PERIOD_ANNUAL)

    by_yymm = {p.stac_yymm: p for p in points}
    assert by_yymm["202312"].price == 70000.0
    assert by_yymm["202412"].price == 53000.0


def test_enrich_price_none_when_no_candle_before_period_end() -> None:
    """가장 오래된 일봉보다 앞선 결산기는 price None."""
    rows = [_row("202012", "100", PERIOD_ANNUAL), _row("202312", "200", PERIOD_ANNUAL)]
    candles = [_candle(date(2023, 12, 28), 70000.0)]
    _, points = _service(rows, candles=candles).get_time_series("005930", PERIOD_ANNUAL)

    by_yymm = {p.stac_yymm: p for p in points}
    assert by_yymm["202012"].price is None
    assert by_yymm["202312"].price == 70000.0


# ── 예상실적(컨센서스 추정) append ────────────────────────────────────────────
_ANNUAL_ROWS = [
    _row("202312", "100", PERIOD_ANNUAL),
    _row("202412", "200", PERIOD_ANNUAL),
    _row("202512", "300", PERIOD_ANNUAL),
]
# 확정연도 매출이 DB와 일치 → 안전가드 통과
_GOOD_ESTIMATES = [
    _estimate("202312", False, "100"),
    _estimate("202412", False, "200"),
    _estimate("202512", False, "300"),
    _estimate("202612", True, "400"),
    _estimate("202712", True, "500"),
]


def test_annual_appends_estimate_rows() -> None:
    """연간 뷰: 확정 행 뒤에 추정 행(2026E/2027E) append, is_estimate=True."""
    _, points = _service(_ANNUAL_ROWS, estimates=_GOOD_ESTIMATES).get_time_series("005930", PERIOD_ANNUAL)

    assert [p.stac_yymm for p in points] == ["202312", "202412", "202512", "202612", "202712"]
    assert [p.is_estimate for p in points] == [False, False, False, True, True]
    e2026 = points[3]
    assert e2026.sale_account == Decimal("400")
    assert e2026.eps == 400.0
    assert e2026.price is None  # 미래 → 주가 없음


def test_quarter_does_not_append_estimates() -> None:
    """분기 뷰: 추정치는 연간만 존재 → append 안 함."""
    rows = [_row("202503", "50", PERIOD_QUARTER), _row("202506", "120", PERIOD_QUARTER)]
    _, points = _service(rows, estimates=_GOOD_ESTIMATES).get_time_series("005930", PERIOD_QUARTER)

    assert all(not p.is_estimate for p in points)


def test_estimate_appends_even_when_confirmed_revenue_differs() -> None:
    """금융지주처럼 추정 매출 정의가 손익계산서와 달라도(≈3배 차이) 추정 행은 붙는다.

    estimate=영업수익 vs income-statement=총영업수익이라 cross-source 대조는 무의미.
    """
    financial = [
        _estimate("202312", False, "232759"),  # 손익계산서(_ANNUAL_ROWS=100)와 전혀 다름
        _estimate("202412", False, "241166"),
        _estimate("202512", False, "224597"),
        _estimate("202612", True, "231461"),
        _estimate("202712", True, "244928"),
    ]
    _, points = _service(_ANNUAL_ROWS, estimates=financial).get_time_series("086790", PERIOD_ANNUAL)

    estimates = [p for p in points if p.is_estimate]
    assert [p.stac_yymm for p in estimates] == ["202612", "202712"]
    assert estimates[0].sale_account == Decimal("231461")


def test_estimate_best_effort_on_client_error() -> None:
    """estimate client 예외 → 추정 없이 확정 행만 정상 반환(상세조회 유지)."""
    _, points = _service(_ANNUAL_ROWS, estimate_raises=True).get_time_series("005930", PERIOD_ANNUAL)

    assert [p.stac_yymm for p in points] == ["202312", "202412", "202512"]
    assert all(not p.is_estimate for p in points)
