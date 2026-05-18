"""DART OpenAPI thin wrapper.

OpenDartReader를 통해 종목코드로 기업개황·정기보고서 데이터를 조회한다.

설계 메모:
- corp_code 매핑이 실패하면 (예: 신규 상장 직후 corpCode.xml 미반영) None 반환.
- 일시적 네트워크 오류는 tenacity 재시도, 영구 실패는 None.
- OpenDartReader 인스턴스는 첫 호출 시 corpCode.xml(~수십 MB)을 자동 다운로드해 메모리에
  캐싱하므로 DI Singleton으로 1회만 생성.
"""

from dataclasses import dataclass
from datetime import date, datetime
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


@dataclass(frozen=True)
class TreasuryStockStatus:
    """DART `stockTotqySttus`(주식의 총수 현황)에서 추출한 자사주 현황."""

    stock_code: str
    stlm_dt: date
    reprt_code: str
    issued_shares: int       # 발행주식 총수 (합계)
    treasury_shares: int     # 자기주식 수 (합계)
    rcept_no: str | None


class DartCompanyClient:
    """OpenDartReader 래퍼 — 종목코드 기반 DART OpenAPI 호출."""

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_treasury_stock_status(
            self, stock_code: str, bsns_year: int, reprt_code: str,
    ) -> TreasuryStockStatus | None:
        """정기보고서 "주식의 총수 현황"(stockTotqySttus) 조회 → 자사주 현황 추출.

        Args:
            stock_code: 종목코드 (예: '005930')
            bsns_year: 사업연도 (예: 2024)
            reprt_code: 11011 사업 / 11012 반기 / 11013 1분기 / 11014 3분기

        Returns:
            합계 행 기준 자사주 현황. 해당 보고서 미발행/응답 비정상이면 None.

        주의:
            우선주 발행이 없는 종목은 "합계" 행 대신 "보통주" 행만 존재할 수 있어 폴백.
        """
        try:
            df = self._reader.report(stock_code, "주식총수", str(bsns_year), reprt_code)
        except ValueError:
            # corp_code 매핑 실패 ("could not find ..."): 신규 상장 직후 등
            return None

        if df is None or df.empty:
            return None

        # '합계' 행 우선, 없으면 '보통주' 행
        total = df[df["se"] == "합계"]
        if total.empty:
            total = df[df["se"] == "보통주"]
        if total.empty:
            return None

        row = total.iloc[0]
        issued = _parse_int(row.get("istc_totqy"))
        treasury = _parse_int(row.get("tesstk_co"))
        stlm_dt = _parse_dart_date(row.get("stlm_dt"))

        if issued is None or issued <= 0 or treasury is None or stlm_dt is None:
            return None

        rcept_no_raw = row.get("rcept_no")
        rcept_no = str(rcept_no_raw) if rcept_no_raw else None

        return TreasuryStockStatus(
            stock_code=stock_code,
            stlm_dt=stlm_dt,
            reprt_code=reprt_code,
            issued_shares=issued,
            treasury_shares=treasury,
            rcept_no=rcept_no,
        )


def _parse_int(value: object) -> int | None:
    """콤마 포함 숫자 문자열을 int로. 빈 값/`-`는 None."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_dart_date(value: object) -> date | None:
    """DART 결산일 문자열(`YYYY-MM-DD`) → date. 실패 시 None."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
