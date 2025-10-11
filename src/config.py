"""
비트코인 자동매매 시스템 설정 모듈

환경변수를 로드하고 설정값을 검증하는 기능을 제공합니다.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 디렉토리 경로
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / "config" / "genie" / ".env"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding='utf-8',
        extra='ignore'
    )

    upbit_access_key: str = Field(
        ...,
        min_length=1,
        description="업비트 액세스 키",
        alias="UPBIT_ACCESS_KEY"
    )

    upbit_secret_key: str = Field(
        ...,
        min_length=1,
        description="업비트 시크릿 키",
        alias="UPBIT_SECRET_KEY"
    )
