"""Config 클래스 테스트"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import UpbitConfig


class TestConfig:
    """Config 클래스 테스트"""

    def test_필수_필드_모두_있으면_생성_성공(self):
        """필수 필드가 모두 제공되면 Config 인스턴스가 생성된다"""
        with patch.dict(os.environ, {
            'UPBIT_ACCESS_KEY': 'test_access_key',
            'UPBIT_SECRET_KEY': 'test_secret_key',
        }):
            config = UpbitConfig(_env_file='nonexistent.env')

            assert config.upbit_access_key == 'test_access_key'
            assert config.upbit_secret_key == 'test_secret_key'

    def test_필수_필드_누락시_ValidationError_발생(self):
        """필수 필드가 누락되면 ValidationError가 발생한다"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                UpbitConfig(_env_file='nonexistent.env')

            errors = exc_info.value.errors()
            error_fields = {error['loc'][0] for error in errors}

            assert 'UPBIT_ACCESS_KEY' in error_fields
            assert 'UPBIT_SECRET_KEY' in error_fields

    def test_upbit_access_key만_누락시_ValidationError_발생(self):
        """upbit_access_key만 누락되면 ValidationError가 발생한다"""
        with patch.dict(os.environ, {
            'UPBIT_SECRET_KEY': 'test_secret_key',
        }, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                UpbitConfig(_env_file='nonexistent.env')

            errors = exc_info.value.errors()
            error_fields = {error['loc'][0] for error in errors}

            assert 'UPBIT_ACCESS_KEY' in error_fields
            assert 'UPBIT_SECRET_KEY' not in error_fields

    def test_upbit_secret_key만_누락시_ValidationError_발생(self):
        """upbit_secret_key만 누락되면 ValidationError가 발생한다"""
        with patch.dict(os.environ, {
            'UPBIT_ACCESS_KEY': 'test_access_key',
        }, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                UpbitConfig(_env_file='nonexistent.env')

            errors = exc_info.value.errors()
            error_fields = {error['loc'][0] for error in errors}

            assert 'UPBIT_SECRET_KEY' in error_fields
            assert 'UPBIT_ACCESS_KEY' not in error_fields

    def test_빈_문자열은_필수_필드로_인정되지_않음(self):
        """빈 문자열은 필수 필드의 유효한 값으로 인정되지 않는다"""
        with patch.dict(os.environ, {
            'UPBIT_ACCESS_KEY': '',
            'UPBIT_SECRET_KEY': 'test_secret_key',
        }, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                UpbitConfig(_env_file='nonexistent.env')

            errors = exc_info.value.errors()
            error_fields = {error['loc'][0] for error in errors}

            assert 'UPBIT_ACCESS_KEY' in error_fields

    def test_환경변수가_env_파일보다_우선순위_높음(self):
        """환경변수의 값이 .env 파일보다 우선한다"""
        with patch.dict(os.environ, {
            'UPBIT_ACCESS_KEY': 'env_access_key',
            'UPBIT_SECRET_KEY': 'env_secret_key',
        }):
            config = UpbitConfig()

            assert config.upbit_access_key == 'env_access_key'
            assert config.upbit_secret_key == 'env_secret_key'

    def test_Config_호출시_기본_env_파일_로드(self):
        """Config()만 호출하면 기본 .env 파일(config/genie/.env)을 읽는다"""
        with patch.dict(os.environ, {}, clear=True):
            config = UpbitConfig()

            # config/genie/.env 파일의 값을 읽어야 함 (값 존재 여부만 확인)
            assert config.upbit_access_key is not None
            assert len(config.upbit_access_key) > 0
            assert config.upbit_secret_key is not None
            assert len(config.upbit_secret_key) > 0
