"""한국투자증권 API 테스트"""

from src.config import HantuConfig
from src.hantu.hantu_api import HantuAPI
from src.hantu.model import AccountType


class TestHantuAPIInit:
    """HantuAPI 초기화 테스트"""

    def test_init_with_real_account(self):
        """실제 계좌로 초기화 시 실제 계좌 설정 사용"""
        # Given
        config = HantuConfig()

        # When
        api = HantuAPI(config, AccountType.REAL)

        # Then
        assert api.account_type == AccountType.REAL
        assert api.cano == config.cano
        assert api.acnt_prdt_cd == config.acnt_prdt_cd
        assert api.app_key == config.app_key
        assert api.app_secret == config.app_secret
        assert api.url_base == config.url_base
        assert api.token_path == config.token_path

    def test_init_with_virtual_account(self):
        """가상 계좌로 초기화 시 가상 계좌 설정 사용"""
        # Given
        config = HantuConfig()

        # When
        api = HantuAPI(config, AccountType.VIRTUAL)

        # Then
        assert api.account_type == AccountType.VIRTUAL
        assert api.cano == config.v_cano
        assert api.acnt_prdt_cd == config.v_acnt_prdt_cd
        assert api.app_key == config.v_app_key
        assert api.app_secret == config.v_app_secret
        assert api.url_base == config.v_url_base
        assert api.token_path == config.v_token_path

    def test_real_and_virtual_use_different_configs(self):
        """실제 계좌와 가상 계좌가 서로 다른 설정 사용"""
        # Given
        config = HantuConfig()

        # When
        real_api = HantuAPI(config, AccountType.REAL)
        virtual_api = HantuAPI(config, AccountType.VIRTUAL)

        # Then
        assert real_api.app_key != virtual_api.app_key
        assert real_api.app_secret != virtual_api.app_secret
        assert real_api.url_base != virtual_api.url_base
        assert real_api.cano != virtual_api.cano
