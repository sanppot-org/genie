"""IncomeStatementSyncService 증분 가드 기준 함수 테스트."""

from datetime import date

from src.service.income_statement_sync_service import (
    _latest_expected_annual_stac_yymm,
    _latest_expected_quarter_stac_yymm,
)


def test_expected_quarter_boundaries() -> None:
    """분기 보고서 마감 경계별 기대 결산년월."""
    assert _latest_expected_quarter_stac_yymm(date(2026, 3, 1)) == "202509"   # 전년 Q3
    assert _latest_expected_quarter_stac_yymm(date(2026, 4, 8)) == "202512"   # 전년말
    assert _latest_expected_quarter_stac_yymm(date(2026, 5, 22)) == "202603"  # 당년 Q1
    assert _latest_expected_quarter_stac_yymm(date(2026, 8, 22)) == "202606"  # 반기
    assert _latest_expected_quarter_stac_yymm(date(2026, 11, 22)) == "202609"  # Q3


def test_expected_annual_boundaries() -> None:
    """사업보고서(연간) 마감 경계별 기대 결산년월."""
    assert _latest_expected_annual_stac_yymm(date(2026, 3, 1)) == "202412"  # 마감 전 → 전전년
    assert _latest_expected_annual_stac_yymm(date(2026, 4, 8)) == "202512"  # 마감 후 → 전년
    assert _latest_expected_annual_stac_yymm(date(2026, 12, 31)) == "202512"
