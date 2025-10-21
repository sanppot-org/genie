from unittest.mock import MagicMock, patch

import pytest

from src.common.healthcheck.client import HealthcheckClient
from src.config import HealthcheckConfig


class TestHealthcheckClient:
    """HealthcheckClient 테스트"""

    @pytest.fixture
    def config_enabled(self) -> HealthcheckConfig:
        """헬스체크가 활성화된 설정"""
        config = MagicMock(spec=HealthcheckConfig)
        config.healthcheck_url = "https://hc-ping.com/test-uuid"
        return config

    @pytest.fixture
    def config_disabled(self) -> HealthcheckConfig:
        """헬스체크가 비활성화된 설정"""
        config = MagicMock(spec=HealthcheckConfig)
        config.healthcheck_url = None
        return config

    def test_is_enabled_활성화된_경우(self, config_enabled: HealthcheckConfig) -> None:
        """헬스체크 URL이 설정된 경우 활성화 상태를 반환한다"""
        client = HealthcheckClient(config_enabled)
        assert client.is_enabled() is True

    def test_is_enabled_비활성화된_경우(self, config_disabled: HealthcheckConfig) -> None:
        """헬스체크 URL이 없는 경우 비활성화 상태를 반환한다"""
        client = HealthcheckClient(config_disabled)
        assert client.is_enabled() is False

    @patch("src.common.healthcheck.client.requests.get")
    def test_ping_성공(self, mock_get: MagicMock, config_enabled: HealthcheckConfig) -> None:
        """ping() 호출 시 올바른 URL로 GET 요청을 보낸다"""
        client = HealthcheckClient(config_enabled)
        client.ping()

        mock_get.assert_called_once_with("https://hc-ping.com/test-uuid", timeout=10)

    @patch("src.common.healthcheck.client.requests.get")
    def test_ping_비활성화된_경우_요청하지_않음(self, mock_get: MagicMock, config_disabled: HealthcheckConfig) -> None:
        """헬스체크가 비활성화된 경우 ping을 보내지 않는다"""
        client = HealthcheckClient(config_disabled)
        client.ping()

        mock_get.assert_not_called()

    @patch("src.common.healthcheck.client.requests.get")
    def test_ping_fail_성공(self, mock_get: MagicMock, config_enabled: HealthcheckConfig) -> None:
        """ping_fail() 호출 시 /fail 엔드포인트로 GET 요청을 보낸다"""
        client = HealthcheckClient(config_enabled)
        client.ping_fail()

        mock_get.assert_called_once_with("https://hc-ping.com/test-uuid/fail", timeout=10)

    @patch("src.common.healthcheck.client.requests.get")
    def test_ping_fail_비활성화된_경우_요청하지_않음(self, mock_get: MagicMock, config_disabled: HealthcheckConfig) -> None:
        """헬스체크가 비활성화된 경우 ping_fail을 보내지 않는다"""
        client = HealthcheckClient(config_disabled)
        client.ping_fail()

        mock_get.assert_not_called()
