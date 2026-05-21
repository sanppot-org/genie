"""KisCompanyClient 단위 테스트 — HantuDomesticAPI mock."""

from unittest.mock import MagicMock

import pytest
import requests
from tenacity import wait_none

from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.search_stock_info import (
    ResponseBody,
    SearchStockInfoOutput,
)
from src.providers.kis_company_client import KisCompanyClient, KisIndustryInfo


def _make_response(**output_kwargs: str | None) -> ResponseBody:
    """KIS 정상 응답 stub — rt_cd='0' + output 필드 주입."""
    return ResponseBody(
        rt_cd="0",
        msg_cd="MCA00000",
        msg1="정상처리",
        output=SearchStockInfoOutput(**output_kwargs),
    )


def test_fetch_industry_info_returns_all_fields_on_success() -> None:
    """정상 응답에서 8개 필드를 모두 KisIndustryInfo로 반환."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.search_stock_info.return_value = _make_response(
        std_idst_clsf_cd_name="제조업",
        std_idst_clsf_cd="C26",
        idx_bztp_lcls_cd="001",
        idx_bztp_lcls_cd_name="전기·전자",
        idx_bztp_mcls_cd="010",
        idx_bztp_mcls_cd_name="반도체",
        idx_bztp_scls_cd="100",
        idx_bztp_scls_cd_name="반도체",
    )
    client = KisCompanyClient(api)

    info = client.fetch_industry_info("005930")

    assert info == KisIndustryInfo(
        industry_code="C26",
        industry_name="제조업",
        sector_large_code="001",
        sector_large_name="전기·전자",
        sector_mid_code="010",
        sector_mid_name="반도체",
        sector_small_code="100",
        sector_small_name="반도체",
    )
    api.search_stock_info.assert_called_once_with("005930")


def test_fetch_industry_info_normalizes_empty_strings_to_none() -> None:
    """KIS가 빈 문자열로 반환하는 필드는 None으로 정규화 (ETF처럼 섹터 누락 케이스)."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.search_stock_info.return_value = _make_response(
        std_idst_clsf_cd_name="",
        std_idst_clsf_cd="",
        idx_bztp_lcls_cd_name="",
    )
    client = KisCompanyClient(api)

    info = client.fetch_industry_info("069500")

    assert info == KisIndustryInfo(
        industry_code=None,
        industry_name=None,
        sector_large_code=None,
        sector_large_name=None,
        sector_mid_code=None,
        sector_mid_name=None,
        sector_small_code=None,
        sector_small_name=None,
    )


def test_fetch_industry_info_returns_none_on_kis_api_error() -> None:
    """KIS가 rt_cd 비정상 → HantuDomesticAPI._validate_response가 raise → None 반환."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.search_stock_info.side_effect = Exception("Error: rt_cd=1, msg=잘못된 종목코드")
    client = KisCompanyClient(api)

    info = client.fetch_industry_info("999999")

    assert info is None


def test_fetch_industry_info_retries_on_request_exception_and_raises() -> None:
    """일시 네트워크 오류는 재시도, 3회 모두 실패하면 예외 전파."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.search_stock_info.side_effect = requests.ConnectionError("boom")
    client = KisCompanyClient(api)

    original_wait = KisCompanyClient.fetch_industry_info.retry.wait  # type: ignore[attr-defined]
    KisCompanyClient.fetch_industry_info.retry.wait = wait_none()  # type: ignore[attr-defined]
    try:
        with pytest.raises(requests.ConnectionError):
            client.fetch_industry_info("005930")
        assert api.search_stock_info.call_count == 3
    finally:
        KisCompanyClient.fetch_industry_info.retry.wait = original_wait  # type: ignore[attr-defined]
