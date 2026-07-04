"""HantuBaseAPI._request 공통 요청 헬퍼 테스트.

연결 레벨 실패를 HantuConnectionError로 번역하고, 기본 timeout을 강제하는지 검증.
"""
import pytest
import requests

from src.config import HantuConfig
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.exceptions import HantuConnectionError
from src.hantu.model.domestic.account_type import AccountType


class TestRequestHelper:
    def _api(self) -> HantuDomesticAPI:
        return HantuDomesticAPI(HantuConfig(), AccountType.VIRTUAL)

    def test_connection_error_translated(self, mocker):
        api = self._api()
        mocker.patch("requests.get", side_effect=requests.ConnectionError("연결 거부"))
        with pytest.raises(HantuConnectionError):
            api._request("get", "http://example.test")

    def test_timeout_translated(self, mocker):
        api = self._api()
        mocker.patch("requests.post", side_effect=requests.Timeout("타임아웃"))
        with pytest.raises(HantuConnectionError):
            api._request("post", "http://example.test")

    def test_default_timeout_injected(self, mocker):
        api = self._api()
        mock_get = mocker.patch("requests.get", return_value=mocker.Mock())
        api._request("get", "http://example.test")
        assert mock_get.call_args.kwargs["timeout"] == (5, 30)

    def test_explicit_timeout_preserved(self, mocker):
        api = self._api()
        mock_get = mocker.patch("requests.get", return_value=mocker.Mock())
        api._request("get", "http://example.test", timeout=1)
        assert mock_get.call_args.kwargs["timeout"] == 1

    def test_non_connection_exception_passthrough(self, mocker):
        api = self._api()
        mocker.patch("requests.get", side_effect=ValueError("기타 오류"))
        with pytest.raises(ValueError):
            api._request("get", "http://example.test")
