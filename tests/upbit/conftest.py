"""업비트 API 테스트 공통 fixture"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_upbit_config():
    """UpbitConfig Mock fixture"""
    with patch("src.upbit.upbit_api.UpbitConfig"):
        mock_config = MagicMock()
        mock_config.upbit_access_key = "test_access"
        mock_config.upbit_secret_key = "test_secret"
        yield mock_config


@pytest.fixture
def mock_upbit_instance():
    """pyupbit.Upbit 인스턴스 Mock fixture"""
    mock_instance = MagicMock()
    return mock_instance


@pytest.fixture
def mock_upbit_class(mock_upbit_instance):
    """pyupbit.Upbit 클래스 Mock fixture"""
    with patch("src.upbit.upbit_api.pyupbit.Upbit") as mock_class:
        mock_class.return_value = mock_upbit_instance
        yield mock_class
