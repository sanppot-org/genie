"""KIS 주식기본조회 wrapper — 종목 업종/섹터 분류 추출.

HantuDomesticAPI(`search_stock_info`)를 wrap해 종목 → 업종 8필드 매핑만 노출한다.
DartCompanyClient의 best-effort 패턴(네트워크 오류 retry / 그 외는 None 반환)을 그대로 따른다.
"""

from dataclasses import dataclass
import logging

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.hantu.domestic_api import HantuDomesticAPI

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KisIndustryInfo:
    """KIS에서 가져온 업종/섹터 메타데이터.

    `industry_*`는 KSIC(한국표준산업분류), `sector_*`는 KIS 자체 지수업종 3단 분류.
    어떤 필드든 KIS 응답에서 비어 있을 수 있으며 None이 허용된다.
    """

    industry_code: str | None
    industry_name: str | None
    sector_large_code: str | None
    sector_large_name: str | None
    sector_mid_code: str | None
    sector_mid_name: str | None
    sector_small_code: str | None
    sector_small_name: str | None


class KisCompanyClient:
    """KIS 주식기본조회 client."""

    def __init__(self, api: HantuDomesticAPI) -> None:
        self._api = api

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_industry_info(self, ticker: str) -> KisIndustryInfo | None:
        """종목 업종 정보 조회.

        - 일시 네트워크 오류는 재시도 후 최종 실패 시 예외 전파
        - KIS API 자체 오류(rt_cd != 0, 잘못된 종목코드 등)는 None 반환
        - 응답의 빈 문자열은 None으로 정규화
        """
        try:
            response = self._api.search_stock_info(ticker)
        except requests.RequestException:
            raise
        except Exception as e:
            logger.warning("KIS search_stock_info 실패 (ticker=%s): %s", ticker, e)
            return None

        output = response.output
        return KisIndustryInfo(
            industry_code=output.std_idst_clsf_cd or None,
            industry_name=output.std_idst_clsf_cd_name or None,
            sector_large_code=output.idx_bztp_lcls_cd or None,
            sector_large_name=output.idx_bztp_lcls_cd_name or None,
            sector_mid_code=output.idx_bztp_mcls_cd or None,
            sector_mid_name=output.idx_bztp_mcls_cd_name or None,
            sector_small_code=output.idx_bztp_scls_cd or None,
            sector_small_name=output.idx_bztp_scls_cd_name or None,
        )
