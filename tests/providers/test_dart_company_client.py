"""DartCompanyClient 단위 테스트 — OpenDartReader mock."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from tenacity import wait_none

from src.providers.dart_company_client import DartCompanyClient, DartCompanyInfo


def _make_client_with_mock_reader() -> tuple[DartCompanyClient, MagicMock]:
    """OpenDartReader 생성을 mock한 채로 client 인스턴스를 만든다.

    DartCompanyClient.__init__이 corpCode.xml을 다운받지 않도록 OpenDartReader를 patch.
    """
    mock_reader = MagicMock()
    config = MagicMock()
    config.api_key = "FAKE_KEY"
    with patch("src.providers.dart_company_client.OpenDartReader", return_value=mock_reader):
        client = DartCompanyClient(config)
    return client, mock_reader


def test_fetch_company_info_returns_industry_code_on_success() -> None:
    """정상 응답에서 induty_code를 추출해 DartCompanyInfo로 반환."""
    client, reader = _make_client_with_mock_reader()
    reader.find_corp_code.return_value = "00126380"
    reader.company.return_value = {
        "status": "000",
        "corp_name": "삼성전자",
        "induty_code": "26410",
    }

    info = client.fetch_company_info("005930")

    assert info == DartCompanyInfo(stock_code="005930", industry_code="26410")


def test_fetch_company_info_returns_none_when_corp_code_not_found() -> None:
    """find_corp_code가 None이면 곧바로 None — DART 호출도 하지 않는다."""
    client, reader = _make_client_with_mock_reader()
    reader.find_corp_code.return_value = None

    info = client.fetch_company_info("999999")

    assert info is None
    reader.company.assert_not_called()


def test_fetch_company_info_returns_none_when_dart_returns_non_ok_status() -> None:
    """DART status가 '000'이 아닌 경우 None."""
    client, reader = _make_client_with_mock_reader()
    reader.find_corp_code.return_value = "00126380"
    reader.company.return_value = {"status": "013", "message": "조회된 데이터가 없습니다"}

    info = client.fetch_company_info("005930")

    assert info is None


def test_fetch_company_info_returns_info_with_none_industry_when_field_missing() -> None:
    """induty_code 필드가 없거나 빈 문자열이면 industry_code는 None."""
    client, reader = _make_client_with_mock_reader()
    reader.find_corp_code.return_value = "00126380"
    reader.company.return_value = {"status": "000", "corp_name": "X"}  # induty_code 누락

    info = client.fetch_company_info("005930")

    assert info == DartCompanyInfo(stock_code="005930", industry_code=None)


def test_fetch_company_info_retries_on_request_exception_and_raises() -> None:
    """일시 네트워크 오류는 재시도, 3회 모두 실패하면 예외 전파."""
    client, reader = _make_client_with_mock_reader()
    reader.find_corp_code.return_value = "00126380"
    reader.company.side_effect = requests.ConnectionError("boom")

    original_wait = DartCompanyClient.fetch_company_info.retry.wait  # type: ignore[attr-defined]
    DartCompanyClient.fetch_company_info.retry.wait = wait_none()  # type: ignore[attr-defined]
    try:
        with pytest.raises(requests.ConnectionError):
            client.fetch_company_info("005930")
        assert reader.company.call_count == 3
    finally:
        DartCompanyClient.fetch_company_info.retry.wait = original_wait  # type: ignore[attr-defined]
