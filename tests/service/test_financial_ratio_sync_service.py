"""FinancialRatioSyncService 테스트 — 증분 가드 기준 함수 + sync 핵심 동작."""

from datetime import date
from unittest.mock import MagicMock

from src.providers.kis_financial_ratio_client import FinancialRatioRow
from src.service.financial_ratio_sync_service import (
    FinancialRatioSyncService,
    _latest_expected_annual_stac_yymm,
)


def test_expected_annual_boundaries() -> None:
    """사업보고서(연간) 마감 경계별 기대 결산년월."""
    assert _latest_expected_annual_stac_yymm(date(2026, 3, 1)) == "202412"  # 마감 전 → 전전년
    assert _latest_expected_annual_stac_yymm(date(2026, 4, 8)) == "202512"  # 마감 후 → 전년
    assert _latest_expected_annual_stac_yymm(date(2026, 12, 31)) == "202512"


def _build_service(
        targets: list[tuple[int, str]],
        latest: dict[int, str],
        rows_by_code: dict[str, list[FinancialRatioRow]],
) -> tuple[FinancialRatioSyncService, MagicMock, list]:
    """DB I/O를 우회하고 client만 mock한 서비스 + 적재된 entity 수집 리스트 반환."""
    upserted: list = []

    kis = MagicMock()
    kis.fetch.side_effect = lambda code: rows_by_code[code]

    service = FinancialRatioSyncService(database=MagicMock(), kis_client=kis, throttle_sec=0)
    # DB 접근(세션/Postgres upsert)을 우회: 내부 메서드를 직접 스텁.
    service._load_targets = lambda: targets  # type: ignore[method-assign]
    service._latest_by_ticker = lambda: latest  # type: ignore[method-assign]

    def _commit(entities: list) -> tuple[int, bool]:
        upserted.extend(entities)
        return len(entities), True

    service._commit_chunk = _commit  # type: ignore[method-assign]
    return service, kis, upserted


def test_sync_fetches_and_upserts_all() -> None:
    """skip_current=False(백필)는 전종목 호출 후 모든 행 적재."""
    rows_by_code = {
        "000001": [FinancialRatioRow("202512", roe=17.07, debt_ratio=45.0, reserve_rate=None,
                                     revenue_growth=None, op_growth=None, net_growth=None,
                                     eps=None, bps=None, sps=None)],
        "000002": [FinancialRatioRow("202512", roe=8.0, debt_ratio=None, reserve_rate=None,
                                     revenue_growth=None, op_growth=None, net_growth=None,
                                     eps=None, bps=None, sps=None)],
    }
    service, kis, upserted = _build_service(
        targets=[(1, "000001"), (2, "000002")], latest={}, rows_by_code=rows_by_code,
    )

    result = service.sync(skip_current=False, now=date(2026, 5, 1))

    assert result.ticker_count == 2
    assert result.skipped_current == 0
    assert result.api_calls_attempted == 2
    assert result.rows_upserted == 2
    assert {e.roe for e in upserted} == {17.07, 8.0}
    assert kis.fetch.call_count == 2


def test_sync_skips_current_when_latest_covered() -> None:
    """skip_current=True면 최신 사업보고서 커버 종목은 호출 생략."""
    rows_by_code = {
        "000002": [FinancialRatioRow("202512", roe=8.0, debt_ratio=None, reserve_rate=None,
                                     revenue_growth=None, op_growth=None, net_growth=None,
                                     eps=None, bps=None, sps=None)],
    }
    # 기준일 2026-05-01 → 기대 연간 = 202512. 000001은 이미 커버 → skip, 000002는 미커버.
    service, kis, upserted = _build_service(
        targets=[(1, "000001"), (2, "000002")],
        latest={1: "202512"},
        rows_by_code=rows_by_code,
    )

    result = service.sync(skip_current=True, now=date(2026, 5, 1))

    assert result.skipped_current == 1
    assert result.api_calls_attempted == 1
    assert kis.fetch.call_args_list[0].args == ("000002",)


def test_sync_counts_api_failure_and_continues() -> None:
    """종목별 API 실패는 api_calls_failed로 집계하고 다음 종목 진행."""
    def _fetch(code: str) -> list[FinancialRatioRow]:
        if code == "000001":
            raise Exception("rt_cd=1")
        return [FinancialRatioRow("202512", roe=8.0, debt_ratio=None, reserve_rate=None,
                                  revenue_growth=None, op_growth=None, net_growth=None,
                                  eps=None, bps=None, sps=None)]

    service, kis, upserted = _build_service(
        targets=[(1, "000001"), (2, "000002")], latest={}, rows_by_code={},
    )
    kis.fetch.side_effect = _fetch

    result = service.sync(skip_current=False, now=date(2026, 5, 1))

    assert result.api_calls_attempted == 2
    assert result.api_calls_failed == 1
    assert result.rows_upserted == 1
