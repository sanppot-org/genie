"""KisEstimateClient 단위 테스트 — E-only 추출 + ×10 디코드 + 행순서 매핑."""

from decimal import Decimal
from unittest.mock import MagicMock

from src.hantu.model.domestic import estimate_perform
from src.providers.kis_estimate_client import KisEstimateClient


def _row(*vals: str) -> estimate_perform.EstimateDataRow:
    keys = ["data1", "data2", "data3", "data4", "data5"]
    return estimate_perform.EstimateDataRow(**dict(zip(keys, vals, strict=False)))


def _body(
    output2: list[estimate_perform.EstimateDataRow],
    output3: list[estimate_perform.EstimateDataRow],
    periods: list[str],
) -> estimate_perform.ResponseBody:
    return estimate_perform.ResponseBody(
        rt_cd="0",
        msg_cd="MCA00000",
        msg1="정상처리",
        output2=output2,
        output3=output3,
        output4=[estimate_perform.EstimatePeriodRow(dt=p) for p in periods],
    )


def _full_body() -> estimate_perform.ResponseBody:
    """확정 3년(2023~2025) + 추정 2년(2026E/2027E) 합성 매트릭스."""
    periods = ["2023.12", "2024.12", "2025.12", "2026.12E", "2027.12E"]
    output2 = [
        _row("100", "200", "300", "400", "500"),     # r0 매출액
        _row("0", "1000", "500", "333", "250"),      # r1 매출증가율(×10) — 내부정합성 검증 대상
        _row("10", "20", "30", "40", "50"),          # r2 영업이익
        _row("0", "0", "0", "0", "0"),               # r3 영업이익증가율(미사용)
        _row("5", "15", "25", "35", "45"),           # r4 순이익
        _row("0", "0", "0", "0", "0"),               # r5 순이익증가율(미사용)
    ]
    output3 = [
        _row("0", "0", "0", "0", "0"),                   # r0 EBITDA(미사용)
        _row("1000", "2000", "3000", "4000", "5000"),    # r1 EPS ×10
        _row("0", "0", "0", "0", "0"),                   # r2 EPS증가율(미사용)
        _row("100", "150", "200", "250", "300"),         # r3 PER ×10
        _row("0", "0", "0", "0", "0"),                   # r4
        _row("0", "0", "0", "0", "0"),                   # r5
        _row("0", "0", "0", "0", "0"),                   # r6
        _row("0", "0", "0", "0", "0"),                   # r7
    ]
    return _body(output2, output3, periods)


def _client(body: estimate_perform.ResponseBody) -> KisEstimateClient:
    api = MagicMock()
    api.estimate_perform.return_value = body
    return KisEstimateClient(api)


def test_fetch_parses_all_periods_with_estimate_flags() -> None:
    points = _client(_full_body()).fetch("005930")

    assert [p.stac_yymm for p in points] == ["202312", "202412", "202512", "202612", "202712"]
    assert [p.is_estimate for p in points] == [False, False, False, True, True]


def test_estimate_columns_decoded() -> None:
    """추정 컬럼: 금액 그대로, EPS/PER은 ÷10."""
    points = _client(_full_body()).fetch("005930")
    e2026 = next(p for p in points if p.stac_yymm == "202612")

    assert e2026.revenue == Decimal("400")
    assert e2026.operating_profit == Decimal("40")
    assert e2026.net_income == Decimal("35")
    assert e2026.eps == 400.0   # 4000 / 10
    assert e2026.per == 25.0    # 250 / 10


def test_confirmed_columns_carry_revenue_for_guard() -> None:
    """확정 기간은 is_estimate=False + revenue 보유(안전가드 대조용)."""
    points = _client(_full_body()).fetch("005930")
    confirmed = {p.stac_yymm: p.revenue for p in points if not p.is_estimate}

    assert confirmed == {"202312": Decimal("100"), "202412": Decimal("200"), "202512": Decimal("300")}


def test_uncovered_stock_returns_empty() -> None:
    """미커버 종목(빈 응답) → []."""
    assert _client(_body([], [], [])).fetch("060310") == []


def test_insufficient_output2_returns_empty() -> None:
    """핵심 손익(output2) 행 부족 → []."""
    body = _body([_row("100", "200")], [_row("1", "2")], ["2025.12", "2026.12E"])
    assert _client(body).fetch("005930") == []


def test_partial_output3_keeps_core_drops_missing_per() -> None:
    """output3가 짧아 PER 행이 없어도(예: SK하이닉스 3행) 매출/영업이익/순이익+EPS는 반환, PER만 None."""
    periods = ["2024.12", "2025.12", "2026.12E"]
    output2 = [
        _row("200", "300", "400"),   # r0 매출
        _row("0", "500", "333"),     # r1 매출증가율(×10) — 정합
        _row("20", "30", "40"),      # r2 영업이익
        _row("0", "0", "0"),
        _row("15", "25", "35"),      # r4 순이익
    ]
    output3 = [
        _row("0", "0", "0"),                 # r0
        _row("2000", "3000", "4000"),        # r1 EPS ×10 (PER 행은 없음)
        _row("0", "0", "0"),                 # r2
    ]
    points = _client(_body(output2, output3, periods)).fetch("000660")
    e2026 = next(p for p in points if p.stac_yymm == "202612")

    assert e2026.is_estimate is True
    assert e2026.revenue == Decimal("400")
    assert e2026.operating_profit == Decimal("40")
    assert e2026.net_income == Decimal("35")
    assert e2026.eps == 400.0   # 4000 / 10
    assert e2026.per is None    # PER 행 없음 → None (전체 버리지 않음)


def test_inconsistent_revenue_growth_returns_empty() -> None:
    """매출 행 YoY와 매출증가율 행이 모순(행순서 의심) → 전체 skip."""
    periods = ["2024.12", "2025.12", "2026.12E"]
    output2 = [
        _row("100", "200", "300"),   # r0: +100%, +50% 변동
        _row("0", "0", "0"),         # r1: 증가율 0 (모순)
        _row("10", "20", "30"),      # r2 영업이익
        _row("0", "0", "0"),
        _row("5", "15", "25"),       # r4 순이익
    ]
    assert _client(_body(output2, [], periods)).fetch("005930") == []
