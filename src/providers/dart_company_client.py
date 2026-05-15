"""DART OpenAPI `company` endpoint thin wrapper.

OpenDartReader를 통해 종목코드로 기업개황을 조회하고, 우리가 필요한 필드(`industry_code`)만
뽑아 도메인 dataclass로 변환한다.

설계 메모:
- corp_code 매핑이 실패하면 (예: 신규 상장 직후 corpCode.xml 미반영) None 반환.
- 일시적 네트워크 오류는 tenacity 재시도, 영구 실패는 None.
- OpenDartReader 인스턴스는 첫 호출 시 corpCode.xml(~수십 MB)을 자동 다운로드해 메모리에
  캐싱하므로 DI Singleton으로 1회만 생성.
"""

from dataclasses import dataclass
import logging

from opendartreader import OpenDartReader
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import OpenDartConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DartCompanyInfo:
    """DART에서 가져온 기업 메타데이터 (필요한 필드만)."""

    stock_code: str
    industry_code: str | None


class DartCompanyClient:
    """OpenDartReader 래퍼 — 종목코드 기반 기업개황 조회."""

    def __init__(self, config: OpenDartConfig) -> None:
        self._reader = OpenDartReader(config.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_company_info(self, stock_code: str) -> DartCompanyInfo | None:
        """기업개황 조회.

        - 매핑 실패(corp_code 못 찾음)·DART 응답이 정상이 아닌 경우 None 반환
        - 네트워크/일시 오류는 재시도 후 최종 실패 시 예외 전파
        """
        corp_code = self._reader.find_corp_code(stock_code)
        if corp_code is None:
            return None

        info = self._reader.company(stock_code)
        if not isinstance(info, dict):
            return None
        # DART는 정상 응답일 때만 'status'='000'을 반환 (또는 status 키 자체가 없는 정상 dict)
        status = info.get("status")
        if status is not None and status != "000":
            logger.warning("DART company API non-OK status for %s: %s (%s)", stock_code, status, info.get("message"))
            return None

        return DartCompanyInfo(
            stock_code=stock_code,
            industry_code=info.get("induty_code") or None,
        )
