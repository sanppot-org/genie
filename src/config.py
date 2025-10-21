"""
자동매매 시스템 설정 모듈

환경변수를 로드하고 설정값을 검증하는 기능을 제공합니다.
업비트와 한국투자증권 API 설정을 관리합니다.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import UTF_8

# 프로젝트 루트 디렉토리 경로
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / "config" / "genie" / ".env"


class UpbitConfig(BaseSettings):
    """업비트 API 설정"""

    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), env_file_encoding=UTF_8, extra="ignore")

    upbit_access_key: str = Field(..., min_length=1, description="업비트 액세스 키", alias="UPBIT_ACCESS_KEY")

    upbit_secret_key: str = Field(..., min_length=1, description="업비트 시크릿 키", alias="UPBIT_SECRET_KEY")


class HantuConfig(BaseSettings):
    """한국투자증권 API 설정"""

    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), env_file_encoding=UTF_8, extra="ignore")

    # 한국투자증권 실계좌 설정
    cano: str = Field(..., min_length=1, description="한국투자증권 계좌번호", alias="CANO")

    acnt_prdt_cd: str = Field(..., min_length=1, description="한국투자증권 계좌상품코드", alias="ACNT_PRDT_CD")

    app_key: str = Field(..., min_length=1, description="한국투자증권 앱 키", alias="APP_KEY")

    app_secret: str = Field(..., min_length=1, description="한국투자증권 앱 시크릿", alias="APP_SECRET")

    url_base: str = Field(..., min_length=1, description="한국투자증권 API 기본 URL", alias="URL_BASE")

    token_path: str = Field(..., min_length=1, description="한국투자증권 토큰 저장 경로", alias="TOKEN_PATH")

    # 한국투자증권 가상계좌 설정
    v_cano: str = Field(..., min_length=1, description="한국투자증권 가상계좌번호", alias="V_CANO")

    v_acnt_prdt_cd: str = Field(..., min_length=1, description="한국투자증권 가상계좌상품코드", alias="V_ACNT_PRDT_CD")

    v_app_key: str = Field(..., min_length=1, description="한국투자증권 가상 앱 키", alias="V_APP_KEY")

    v_app_secret: str = Field(..., min_length=1, description="한국투자증권 가상 앱 시크릿", alias="V_APP_SECRET")

    v_url_base: str = Field(..., min_length=1, description="한국투자증권 가상 API 기본 URL", alias="V_URL_BASE")

    v_token_path: str = Field(..., min_length=1, description="한국투자증권 가상 토큰 저장 경로", alias="V_TOKEN_PATH")

    @field_validator("token_path", "v_token_path")
    @classmethod
    def resolve_path(cls, v: str) -> str:
        """상대 경로를 프로젝트 루트 기준 절대 경로로 변환"""
        path = Path(v)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path)


class GoogleSheetConfig(BaseSettings):
    """구글 시트 API 설정"""

    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), env_file_encoding=UTF_8, extra="ignore")

    google_sheet_url: str = Field(..., min_length=1, description="Google Sheet URL", alias="GOOGLE_SHEET_URL")

    credentials_path: str = Field(
        default="config/auto-trade-google-key.json",
        description="Google Service Account Credentials 파일 경로",
        alias="GOOGLE_CREDENTIALS_PATH",
    )

    sheet_name: str = Field(..., min_length=1, description="시트 이름", alias="SHEET_NAME")

    @field_validator("credentials_path")
    @classmethod
    def resolve_credentials_path(cls, v: str) -> str:
        """상대 경로를 프로젝트 루트 기준 절대 경로로 변환"""
        path = Path(v)
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        # 파일 존재 확인
        if not path.exists():
            raise ValueError(f"Credentials 파일을 찾을 수 없습니다: {path}")

        return str(path)


class SlackConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), env_file_encoding=UTF_8, extra="ignore")

    log_url: str = Field(..., min_length=1, description="Slack 로그 url", alias="SLACK_WEBHOOK_URL_GENIE_LOG")
    debug_url: str = Field(..., min_length=1, description="Slack 디버그 url", alias="SLACK_WEBHOOK_URL_GENIE_DEBUG")
    status_url: str = Field(..., min_length=1, description="Slack 에러 url", alias="SLACK_WEBHOOK_URL_GENIE_STATUS")


class HealthcheckConfig(BaseSettings):
    """Healthchecks.io 설정"""

    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), env_file_encoding=UTF_8, extra="ignore")

    healthcheck_url: str | None = Field(default=None, description="Healthchecks.io ping URL (optional)", alias="HEALTHCHECK_URL")


class LogtailConfig(BaseSettings):
    """Better Stack (Logtail) 로깅 설정"""

    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), env_file_encoding=UTF_8, extra="ignore")

    logtail_source_token: str | None = Field(
        default=None,
        description="Better Stack (Logtail) Source Token (optional)",
        alias="LOGTAIL_SOURCE_TOKEN"
    )

    logtail_source_host: str = Field(
        ...,
        description="Better Stack (Logtail) Source Host (optional)",
        alias="LOGTAIL_SOURCE_HOST"
    )
