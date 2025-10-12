"""UpbitAPI와 Config 통합 테스트"""

import os
from unittest.mock import patch

from src.config import UpbitConfig
from src.upbit.upbit_api import UpbitAPI


class TestUpbitAPIConfigIntegration:
    """UpbitAPI와 Config 통합 테스트"""

    def test_Config를_UpbitAPI에_전달_가능(self):
        """Config 인스턴스를 UpbitAPI에 전달할 수 있다"""
        with patch.dict(os.environ, {
            'UPBIT_ACCESS_KEY': 'test_access_key',
            'UPBIT_SECRET_KEY': 'test_secret_key',
        }):
            config = UpbitConfig()
            upbit_api = UpbitAPI(config)

            assert upbit_api.upbit is not None
