"""UpbitAPI와 Config 통합 테스트"""

import os
from unittest.mock import patch

import pytest

from src.config import Config
from src.upbit.upbit_api import UpbitAPI


class TestUpbitAPIConfigIntegration:
    """UpbitAPI와 Config 통합 테스트"""

    def test_Config를_UpbitAPI에_전달_가능(self):
        """Config 인스턴스를 UpbitAPI에 전달할 수 있다"""
        with patch.dict(os.environ, {
            'UPBIT_ACCESS_KEY': 'test_access_key',
            'UPBIT_SECRET_KEY': 'test_secret_key',
        }):
            config = Config()
            upbit_api = UpbitAPI(config)

            assert upbit_api.upbit is not None

    def test_Config에_키가_없으면_UpbitAPI_생성_실패(self):
        """Config에 필수 키가 없으면 UpbitAPI 생성이 실패한다"""
        with patch.dict(os.environ, {
            'UPBIT_ACCESS_KEY': 'test_access_key',
            'UPBIT_SECRET_KEY': 'test_secret_key',
        }):
            config = Config()

            # Config 인스턴스의 키를 None으로 설정 (실제로는 불가능하지만 테스트용)
            with patch.object(config, 'upbit_access_key', None):
                with pytest.raises(ValueError, match="업비트 API 키가 설정되지 않았습니다"):
                    UpbitAPI(config)
