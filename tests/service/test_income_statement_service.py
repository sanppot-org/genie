"""IncomeStatementService 단위 테스트 — 연간 선두행 필터 + 분기 단일환산 + EPS/PER enrich."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

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


def _fund(d: date, eps: float, per: float, dps: float = 0.0, div: float = 0.0, bps: float | None = None) -> StockFundamental:
    return StockFundamental(ticker_id=1, date=d, eps=eps, per=per, dps=dps, div=div, bps=bps)


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


def test_annual_estimates_returns_estimate_rows_only() -> None:
    """연간 추정 조회: 추정 행(2026E/2027E)만 반환(확정행 미포함), is_estimate=True."""
    _, points = _service(_ANNUAL_ROWS, estimates=_GOOD_ESTIMATES).get_annual_estimates("005930")

    assert [p.stac_yymm for p in points] == ["202612", "202712"]
    assert all(p.is_estimate for p in points)
    e2026 = points[0]
    assert e2026.sale_account == Decimal("400")
    assert e2026.eps == 400.0
    assert e2026.price is None  # 캔들 없음 → 최근 종가 없음 → None


def test_get_time_series_excludes_estimates() -> None:
    """확정 시계열(`get_time_series`)은 예상행을 포함하지 않는다 — 예상은 별도 엔드포인트로 분리."""
    _, points = _service(_ANNUAL_ROWS, estimates=_GOOD_ESTIMATES).get_time_series("005930", PERIOD_ANNUAL)

    assert [p.stac_yymm for p in points] == ["202312", "202412", "202512"]
    assert all(not p.is_estimate for p in points)


def test_quarter_has_no_estimates() -> None:
    """분기 뷰: 확정 시계열만(추정치는 연간만 존재하고, get_time_series는 예상을 붙이지 않음)."""
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
    _, points = _service(_ANNUAL_ROWS, estimates=financial).get_annual_estimates("086790")

    estimates = [p for p in points if p.is_estimate]
    assert [p.stac_yymm for p in estimates] == ["202612", "202712"]
    assert estimates[0].sale_account == Decimal("231461")


def test_estimate_best_effort_on_client_error() -> None:
    """estimate client 예외 → 예상행 빈 리스트(확정 시계열은 get_time_series로 별도 제공)."""
    _, points = _service(_ANNUAL_ROWS, estimate_raises=True).get_annual_estimates("005930")

    assert points == []


def test_estimate_price_and_forward_per_from_latest_close() -> None:
    """예상치 행: price=최근 종가, per=최근종가/예상EPS(forward PER)."""
    candles = [
        _candle(date(2024, 12, 30), 53000.0),
        _candle(date(2025, 3, 28), 55000.0),  # 가장 최근 종가
    ]
    estimates = [
        _estimate("202612", True, "400"),   # eps=400.0, per=10.0
        _estimate("202712", True, "500"),   # eps=500.0, per=10.0
    ]
    _, points = _service(_ANNUAL_ROWS, candles=candles, estimates=estimates).get_annual_estimates("005930")

    est_rows = [p for p in points if p.is_estimate]
    assert len(est_rows) == 2
    # price = 최근 종가
    assert est_rows[0].price == 55000.0
    assert est_rows[1].price == 55000.0
    # per = 최근종가 / 예상EPS
    assert est_rows[0].per == pytest.approx(55000.0 / 400.0)
    assert est_rows[1].per == pytest.approx(55000.0 / 500.0)


def test_estimate_derived_eps_per_when_e_eps_none() -> None:
    """e.eps=None 금융지주 등: base_eps·base_ni로 예상EPS 도출 후 forward PER 계산."""
    from src.providers.kis_estimate_client import EstimatePointData

    # 확정 행: eps=5000, net_income=10000(억원)
    rows_with_ni = [
        _row("202312", "100", PERIOD_ANNUAL),
        _row("202412", "200", PERIOD_ANNUAL),
        _row("202512", "300", PERIOD_ANNUAL),
    ]
    # 펀더멘털로 202512 eps=5000 부여
    funds = [_fund(date(2025, 12, 30), eps=5000.0, per=10.0)]
    # 202512 thtr_ntin(net_income) = 10000
    from src.database.models import StockIncomeStatement
    rows_with_ni[2] = StockIncomeStatement(
        ticker_id=1,
        period_type=PERIOD_ANNUAL,
        stac_yymm="202512",
        sale_account=Decimal("300"),
        bsop_prti=Decimal("300"),
        thtr_ntin=Decimal("10000"),  # 억원
    )

    # 추정행: e.eps=None, e.net_income=12000(억원)
    est_no_eps = EstimatePointData(
        stac_yymm="202612",
        is_estimate=True,
        revenue=Decimal("400"),
        operating_profit=Decimal("400"),
        net_income=Decimal("12000"),
        eps=None,
        per=9.0,
    )
    candles = [_candle(date(2025, 12, 30), 60000.0)]

    estimate_client = MagicMock()
    estimate_client.fetch.return_value = [est_no_eps]

    ticker_repo = MagicMock()
    ticker_repo.find_by_ticker.return_value = MagicMock(id=1, ticker="086790", name="하나금융지주")
    income_repo = MagicMock()
    income_repo.find_by_ticker.return_value = rows_with_ni
    fundamental_repo = MagicMock()
    fundamental_repo.find_by_ticker.return_value = funds
    candle_repo = MagicMock()
    candle_repo.find_by_ticker.return_value = candles

    svc = IncomeStatementService(ticker_repo, income_repo, fundamental_repo, candle_repo, estimate_client)
    _, points = svc.get_annual_estimates("086790")

    est_rows = [p for p in points if p.is_estimate]
    assert len(est_rows) == 1
    expected_eps = 5000.0 * (12000.0 / 10000.0)  # = 6000.0
    assert est_rows[0].eps == pytest.approx(expected_eps)
    assert est_rows[0].per == pytest.approx(60000.0 / expected_eps)


def test_estimate_derived_eps_none_when_no_base() -> None:
    """base(eps/ni)를 구할 수 없으면 예상EPS=None, PER은 컨센서스 per 폴백."""
    from src.providers.kis_estimate_client import EstimatePointData

    est_no_eps = EstimatePointData(
        stac_yymm="202612",
        is_estimate=True,
        revenue=Decimal("400"),
        operating_profit=Decimal("400"),
        net_income=Decimal("12000"),
        eps=None,
        per=9.0,
    )
    # 펀더멘털/캔들 없음 → base_eps=None
    estimate_client = MagicMock()
    estimate_client.fetch.return_value = [est_no_eps]

    ticker_repo = MagicMock()
    ticker_repo.find_by_ticker.return_value = MagicMock(id=1, ticker="086790", name="하나금융지주")
    income_repo = MagicMock()
    income_repo.find_by_ticker.return_value = _ANNUAL_ROWS
    fundamental_repo = MagicMock()
    fundamental_repo.find_by_ticker.return_value = []
    candle_repo = MagicMock()
    candle_repo.find_by_ticker.return_value = []

    svc = IncomeStatementService(ticker_repo, income_repo, fundamental_repo, candle_repo, estimate_client)
    _, points = svc.get_annual_estimates("086790")

    est_rows = [p for p in points if p.is_estimate]
    assert len(est_rows) == 1
    assert est_rows[0].eps is None
    assert est_rows[0].per == 9.0  # 컨센서스 per 폴백


def test_estimate_per_fallback_when_eps_none_or_zero() -> None:
    """예상EPS가 None이거나 0이면 컨센서스 per(e.per)로 폴백."""
    candles = [_candle(date(2025, 3, 28), 55000.0)]

    # eps=0 케이스: _estimate 헬퍼가 float(revenue)를 eps로 쓰므로 직접 생성
    from src.providers.kis_estimate_client import EstimatePointData

    est_zero_eps = EstimatePointData(
        stac_yymm="202612",
        is_estimate=True,
        revenue=Decimal("400"),
        operating_profit=Decimal("400"),
        net_income=Decimal("400"),
        eps=0.0,
        per=12.5,
    )
    est_none_eps = EstimatePointData(
        stac_yymm="202712",
        is_estimate=True,
        revenue=Decimal("500"),
        operating_profit=Decimal("500"),
        net_income=Decimal("500"),
        eps=None,
        per=13.0,
    )

    estimate_client = MagicMock()
    estimate_client.fetch.return_value = [est_zero_eps, est_none_eps]

    from src.service.income_statement_service import IncomeStatementService
    ticker_repo = MagicMock()
    ticker_repo.find_by_ticker.return_value = MagicMock(id=1, ticker="005930", name="삼성전자")
    income_repo = MagicMock()
    income_repo.find_by_ticker.return_value = _ANNUAL_ROWS
    fundamental_repo = MagicMock()
    fundamental_repo.find_by_ticker.return_value = []
    candle_repo = MagicMock()
    candle_repo.find_by_ticker.return_value = candles

    svc = IncomeStatementService(ticker_repo, income_repo, fundamental_repo, candle_repo, estimate_client)
    _, points = svc.get_annual_estimates("005930")

    est_rows = [p for p in points if p.is_estimate]
    assert len(est_rows) == 2
    # eps=0 → 폴백
    assert est_rows[0].per == 12.5
    # eps=None → 폴백
    assert est_rows[1].per == 13.0
    # price는 두 경우 모두 최근 종가
    assert est_rows[0].price == 55000.0
    assert est_rows[1].price == 55000.0


# ----- Phase 2e: 주당지표(EPS·DPS) 액면분할 보정 -----

def _candle_adj(d: date, close: float, adj_close: float | None) -> StockDailyCandle:
    return StockDailyCandle(
        ticker_id=1, date=d, open=close, high=close, low=close, close=close,
        volume=1, adj_close=adj_close,
    )


def test_split_adjusts_eps_dps_to_current_share_basis() -> None:
    """50:1 분할 전 결산기 EPS·DPS가 현재 주식수 기준으로 환산돼 절벽이 사라진다."""
    rows = [_row("201712", "100", PERIOD_ANNUAL), _row("201812", "200", PERIOD_ANNUAL)]
    funds = [
        _fund(date(2017, 12, 28), eps=157967.0, per=15.0, dps=28500.0),  # 분할 전
        _fund(date(2018, 12, 28), eps=5997.0, per=6.4, dps=850.0),       # 분할 후
    ]
    candles = [
        _candle_adj(date(2017, 12, 28), close=2_650_000.0, adj_close=53_000.0),  # factor=0.02
        _candle_adj(date(2018, 12, 28), close=53_000.0, adj_close=53_000.0),     # factor=1.0
    ]
    _, points = _service(rows, funds=funds, candles=candles).get_time_series("005930", PERIOD_ANNUAL)

    by = {p.stac_yymm: p for p in points}
    assert by["201712"].eps == pytest.approx(157967.0 * 0.02)  # 3159.34
    assert by["201712"].dps == pytest.approx(28500.0 * 0.02)   # 570.0
    assert by["201812"].eps == pytest.approx(5997.0)           # factor=1, 불변
    assert by["201812"].dps == pytest.approx(850.0)
    # per(저장 비율)·절대금액은 보정 안 함
    assert by["201712"].per == 15.0
    assert by["201712"].sale_account == Decimal("100")


def test_no_adjust_when_adj_close_null() -> None:
    """adj_close 미백필(~2014 이전) 캔들이면 factor 미적용, EPS·DPS 원값 유지."""
    rows = [_row("201212", "100", PERIOD_ANNUAL)]
    funds = [_fund(date(2012, 12, 28), eps=120000.0, per=10.0, dps=8000.0)]
    candles = [_candle_adj(date(2012, 12, 28), close=1_300_000.0, adj_close=None)]
    _, points = _service(rows, funds=funds, candles=candles).get_time_series("005930", PERIOD_ANNUAL)

    p = points[0]
    assert p.eps == 120000.0
    assert p.dps == 8000.0


def test_payout_ratio_preserved_after_split_adjust() -> None:
    """eps·dps에 동일 factor 적용 → 배당성향(dps/eps) 비율 보존."""
    rows = [_row("201712", "100", PERIOD_ANNUAL)]
    funds = [_fund(date(2017, 12, 28), eps=157967.0, per=15.0, dps=28500.0)]
    candles = [_candle_adj(date(2017, 12, 28), close=2_650_000.0, adj_close=53_000.0)]
    _, points = _service(rows, funds=funds, candles=candles).get_time_series("005930", PERIOD_ANNUAL)

    p = points[0]
    assert p.dps / p.eps == pytest.approx(28500.0 / 157967.0)


def test_factor_anchored_to_fundamental_snapshot_date_not_period_end() -> None:
    """분할 경계: factor는 결산말일 캔들이 아니라 'EPS가 나온 fundamental 날짜' 기준.

    period_end(2018-06-30)로 캔들을 bisect하면 분할 후 캔들(factor=1)이 잡혀 EPS가
    보정 안 되지만, EPS는 분할 전(2018-03) 주식수 기준이므로 factor=0.02여야 한다.
    """
    rows = [_row("201806", "100", PERIOD_QUARTER)]
    funds = [_fund(date(2018, 3, 30), eps=100000.0, per=10.0, dps=5000.0)]  # 분할 전 스냅샷
    candles = [
        _candle_adj(date(2018, 3, 30), close=2_500_000.0, adj_close=50_000.0),  # 분할 전 factor=0.02
        _candle_adj(date(2018, 6, 29), close=50_000.0, adj_close=50_000.0),     # 분할 후 factor=1.0
    ]
    _, points = _service(rows, funds=funds, candles=candles).get_time_series(
        "005930", PERIOD_QUARTER, single_quarter=False,
    )

    p = next(p for p in points if p.stac_yymm == "201806")
    # 스냅샷 날짜(2018-03-30) factor=0.02 적용 → 2000. period_end 기준이면 100000(틀림).
    assert p.eps == pytest.approx(2000.0)
    assert p.dps == pytest.approx(100.0)


def test_split_adjusts_bps_to_current_share_basis() -> None:
    """BPS(주당순자산)도 eps·dps와 동일 factor로 보정 → PBR(price/bps) 비율 보존.

    현재 API/프론트 미노출(데이터 계층 보정)이라 IncomeStatementPointData에서만 검증.
    """
    rows = [_row("201712", "100", PERIOD_ANNUAL), _row("201812", "200", PERIOD_ANNUAL)]
    funds = [
        _fund(date(2017, 12, 28), eps=157967.0, per=15.0, dps=28500.0, bps=1_156_530.0),  # 분할 전
        _fund(date(2018, 12, 28), eps=5997.0, per=6.4, dps=850.0, bps=28_126.0),           # 분할 후
    ]
    candles = [
        _candle_adj(date(2017, 12, 28), close=2_650_000.0, adj_close=53_000.0),  # factor=0.02
        _candle_adj(date(2018, 12, 28), close=53_000.0, adj_close=53_000.0),     # factor=1.0
    ]
    _, points = _service(rows, funds=funds, candles=candles).get_time_series("005930", PERIOD_ANNUAL)

    by = {p.stac_yymm: p for p in points}
    assert by["201712"].bps == pytest.approx(1_156_530.0 * 0.02)  # 23130.6 — 절벽 제거
    assert by["201812"].bps == pytest.approx(28_126.0)            # factor=1, 불변
