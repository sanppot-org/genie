"""빗썸 API 테스트"""

from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from src.bithumb.bithumb_api import BithumbApi
from src.bithumb.model import BalanceInfo
from src.common.http_client import make_api_request
from src.config import BithumbConfig


@pytest.fixture
def mock_config():
    """테스트용 BithumbConfig fixture"""
    return BithumbConfig(
        BITHUMB_ACCESS_KEY="test_access_key",
        BITHUMB_SECRET_KEY="test_secret_key"
    )


class TestGetAvailableAmount:
    """get_available_amount 메서드 테스트"""

    def test_KRW_잔고가_있으면_해당_금액_반환(self, mock_config):
        """KRW 잔고가 있으면 해당 금액을 반환한다"""
        # given
        api = BithumbApi(mock_config)
        api.get_balances = MagicMock(
            return_value=[
                BalanceInfo(
                    currency="KRW",
                    balance=500000.0,
                    locked=0.0,
                    avg_buy_price=0.0,
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                ),
                BalanceInfo(
                    currency="BTC",
                    balance=0.1,
                    locked=0.0,
                    avg_buy_price=50000000.0,
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                ),
            ]
        )

        # when
        result = api.get_available_amount("KRW")

        # then
        assert result == 500000.0

    def test_KRW_잔고가_없으면_0_반환(self, mock_config):
        """KRW 잔고가 없으면 0을 반환한다"""
        # given
        api = BithumbApi(mock_config)
        api.get_balances = MagicMock(
            return_value=[
                BalanceInfo(
                    currency="BTC",
                    balance=0.1,
                    locked=0.0,
                    avg_buy_price=50000000.0,
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                )
            ]
        )

        # when
        result = api.get_available_amount("KRW")

        # then
        assert result == 0.0

    def test_다른_통화_잔고_조회(self, mock_config):
        """다른 통화의 잔고도 조회할 수 있다"""
        # given
        api = BithumbApi(mock_config)
        api.get_balances = MagicMock(
            return_value=[
                BalanceInfo(
                    currency="KRW",
                    balance=500000.0,
                    locked=0.0,
                    avg_buy_price=0.0,
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                ),
                BalanceInfo(
                    currency="BTC",
                    balance=0.1,
                    locked=0.0,
                    avg_buy_price=50000000.0,
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                ),
            ]
        )

        # when
        result = api.get_available_amount("BTC")

        # then
        assert result == 0.1

    def test_기본값은_KRW(self, mock_config):
        """currency 파라미터의 기본값은 KRW다"""
        # given
        api = BithumbApi(mock_config)
        api.get_balances = MagicMock(
            return_value=[
                BalanceInfo(
                    currency="KRW",
                    balance=500000.0,
                    locked=0.0,
                    avg_buy_price=0.0,
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                )
            ]
        )

        # when
        result = api.get_available_amount()

        # then
        assert result == 500000.0


class TestMakeApiRequest:
    """make_api_request 함수 테스트 (retry 로직)"""

    @patch("requests.request")
    def test_네트워크_에러_발생_시_재시도_후_성공(self, mock_request):
        """네트워크 에러 발생 시 재시도를 수행하고 성공하면 응답을 반환한다"""
        # given
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        # 처음 2번은 ConnectionError 발생, 3번째에 성공
        mock_request.side_effect = [
            requests.ConnectionError("Connection failed"),
            requests.ConnectionError("Connection failed"),
            mock_response,
        ]

        # when
        response = make_api_request("https://api.bithumb.com/v1/accounts", headers={})

        # then
        assert response.status_code == 200
        assert mock_request.call_count == 3

    @patch("requests.request")
    def test_타임아웃_발생_시_재시도_후_성공(self, mock_request):
        """타임아웃 발생 시 재시도를 수행하고 성공하면 응답을 반환한다"""
        # given
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        # 처음 1번은 Timeout 발생, 2번째에 성공
        mock_request.side_effect = [
            requests.Timeout("Request timeout"),
            mock_response,
        ]

        # when
        response = make_api_request("https://api.bithumb.com/v1/accounts", headers={})

        # then
        assert response.status_code == 200
        assert mock_request.call_count == 2

    @patch("requests.request")
    def test_3회_재시도_후_실패하면_예외_발생(self, mock_request):
        """3회 재시도 후에도 실패하면 예외가 발생한다"""
        # given
        # 3번 모두 ConnectionError 발생
        mock_request.side_effect = requests.ConnectionError("Connection failed")

        # when & then
        with pytest.raises(requests.ConnectionError):
            make_api_request("https://api.bithumb.com/v1/accounts", headers={})

        assert mock_request.call_count == 3

    @patch("requests.request")
    def test_첫_시도에_성공하면_재시도_없음(self, mock_request):
        """첫 시도에 성공하면 재시도를 하지 않는다"""
        # given
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        # when
        response = make_api_request("https://api.bithumb.com/v1/accounts", headers={})

        # then
        assert response.status_code == 200
        assert mock_request.call_count == 1
