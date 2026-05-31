"""KisFinancialRatioClient 단위 테스트 — HantuDomesticAPI mock."""

from unittest.mock import MagicMock

import pytest
from tenacity import wait_none

from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.financial_ratio import FinancialRatioOutput, ResponseBody
from src.providers.kis_financial_ratio_client import KisFinancialRatioClient
from src.providers.kis_income_statement_client import KisRateLimitError


def _resp(*outputs: FinancialRatioOutput) -> ResponseBody:
    return ResponseBody(rt_cd="0", msg_cd="MCA00000", msg1="정상처리", output=list(outputs))


def test_fetch_parses_ratios_and_negatives() -> None:
    """ROE·성장률·부채비율 등을 float로 파싱(음수 포함)."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.financial_ratio.return_value = _resp(
        FinancialRatioOutput(
            stac_yymm="202212",
            grs="-3.5",
            bsop_prfi_inrt="0",     # 적자전환 등 특수값 → 0.0
            ntin_inrt="12.3",
            roe_val="17.07",
            eps="5000",
            sps="40000",
            bps="50000",
            rsrv_rate="1234.5",
            lblt_rate="45.6",
        ),
    )
    client = KisFinancialRatioClient(api)

    rows = client.fetch("005930")

    assert len(rows) == 1
    r = rows[0]
    assert r.stac_yymm == "202212"
    assert r.roe == 17.07
    assert r.revenue_growth == -3.5
    assert r.op_growth == 0.0
    assert r.net_growth == 12.3
    assert r.eps == 5000.0
    assert r.bps == 50000.0
    assert r.sps == 40000.0
    assert r.reserve_rate == 1234.5
    assert r.debt_ratio == 45.6
    api.financial_ratio.assert_called_once_with("005930")


def test_fetch_normalizes_empty_to_none() -> None:
    """빈값/파싱불가는 None."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.financial_ratio.return_value = _resp(
        FinancialRatioOutput(stac_yymm="202212", roe_val="", lblt_rate=None, eps="N/A"),
    )
    client = KisFinancialRatioClient(api)

    r = client.fetch("005930")[0]

    assert r.roe is None
    assert r.debt_ratio is None
    assert r.eps is None


def test_fetch_skips_rows_without_stac_yymm() -> None:
    api = MagicMock(spec=HantuDomesticAPI)
    api.financial_ratio.return_value = _resp(
        FinancialRatioOutput(stac_yymm=None, roe_val="1.0"),
        FinancialRatioOutput(stac_yymm="202212", roe_val="17.07"),
    )
    client = KisFinancialRatioClient(api)

    rows = client.fetch("005930")

    assert [r.stac_yymm for r in rows] == ["202212"]


def test_fetch_returns_empty_on_valid_empty_response() -> None:
    """정상 응답이지만 output 없음 → 빈 리스트 (오류 아님)."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.financial_ratio.return_value = _resp()
    client = KisFinancialRatioClient(api)

    assert client.fetch("005930") == []


def test_fetch_propagates_kis_api_error() -> None:
    """KIS rt_cd 비정상 → 예외 전파(빈 응답과 구분, sync가 api_calls_failed 집계)."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.financial_ratio.side_effect = Exception("Error: rt_cd=1")
    client = KisFinancialRatioClient(api)

    with pytest.raises(Exception, match="rt_cd=1"):
        client.fetch("999999")


def test_fetch_retries_on_rate_limit() -> None:
    """초당 거래건수 초과(EGW00201)는 KisRateLimitError로 재시도(stop_after_attempt=5)."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.financial_ratio.side_effect = Exception(
        'Error: {"rt_cd":"1","msg_cd":"EGW00201","msg1":"초당 거래건수를 초과하였습니다."}'
    )
    client = KisFinancialRatioClient(api)

    original_wait = KisFinancialRatioClient.fetch.retry.wait  # type: ignore[attr-defined]
    KisFinancialRatioClient.fetch.retry.wait = wait_none()  # type: ignore[attr-defined]
    try:
        with pytest.raises(KisRateLimitError):
            client.fetch("005930")
        assert api.financial_ratio.call_count == 5
    finally:
        KisFinancialRatioClient.fetch.retry.wait = original_wait  # type: ignore[attr-defined]
