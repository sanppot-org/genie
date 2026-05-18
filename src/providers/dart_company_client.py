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


@dataclass(frozen=True)
class BuybackEvent:
    """DART 자기주식 취득·처분 결정 공시에서 추출한 이벤트."""

    stock_code: str
    rcept_no: str
    event_type: str          # ACQUISITION / DISPOSAL
    resolution_date: date    # 이사회 결의일
    planned_shares: int | None
    planned_amount: int | None
    period_start: date | None
    period_end: date | None
    purpose: str | None


# DART event() 키워드 → 이벤트 타입 라벨
_BUYBACK_KEYWORD_MAP: tuple[tuple[str, str], ...] = (
    ("자기주식취득", "ACQUISITION"),
    ("자기주식처분", "DISPOSAL"),
)


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


    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_buyback_events(
            self, stock_code: str, from_date: date, to_date: date,
    ) -> list[BuybackEvent]:
        """자기주식 취득·처분 결정 공시 일괄 조회.

        OpenDartReader `event()`로 `자기주식취득`, `자기주식처분` 두 종류를 호출 후 합쳐서 반환.
        corp_code 매핑 실패 / 응답 없음은 빈 리스트.

        Args:
            stock_code: 종목코드 (예: '005930')
            from_date: 시작 접수일 (포함)
            to_date: 종료 접수일 (포함)

        Returns:
            취득·처분 이벤트 리스트. 결의일·접수번호 모두 정상인 row만 포함.
        """
        start = from_date.strftime("%Y%m%d")
        end = to_date.strftime("%Y%m%d")
        results: list[BuybackEvent] = []

        for keyword, event_type in _BUYBACK_KEYWORD_MAP:
            try:
                df = self._reader.event(stock_code, keyword, start, end)
            except ValueError:
                # corp_code 매핑 실패 — 두 keyword 모두 동일하게 실패하므로 즉시 종료
                return []

            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                rcept_no = str(row.get("rcept_no") or "").strip()
                resolution_date = _parse_kor_date(
                    row.get("aq_dd") if event_type == "ACQUISITION" else row.get("dp_dd")
                )
                if not rcept_no or resolution_date is None:
                    continue

                if event_type == "ACQUISITION":
                    planned_shares = _parse_int(row.get("aqpln_stk_ostk"))
                    planned_amount = _parse_int(row.get("aqpln_prc_ostk"))
                    period_start = _parse_kor_date(row.get("aqexpd_bgd"))
                    period_end = _parse_kor_date(row.get("aqexpd_edd"))
                    purpose = _normalize_text(row.get("aq_pp"))
                else:
                    planned_shares = _parse_int(row.get("dppln_stk_ostk"))
                    planned_amount = _parse_int(row.get("dppln_prc_ostk"))
                    period_start = _parse_kor_date(row.get("dpprpd_bgd"))
                    period_end = _parse_kor_date(row.get("dpprpd_edd"))
                    purpose = _normalize_text(row.get("dp_pp"))

                results.append(BuybackEvent(
                    stock_code=stock_code,
                    rcept_no=rcept_no,
                    event_type=event_type,
                    resolution_date=resolution_date,
                    planned_shares=planned_shares,
                    planned_amount=planned_amount,
                    period_start=period_start,
                    period_end=period_end,
                    purpose=purpose,
                ))

        return results


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


def _parse_kor_date(value: object) -> date | None:
    """DART 한글 날짜 문자열(`YYYY년 MM월 DD일`) → date. 빈 값/`-`는 None."""
    if not value:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    try:
        return datetime.strptime(text, "%Y년 %m월 %d일").date()
    except (ValueError, TypeError):
        return None


def _normalize_text(value: object) -> str | None:
    """공백·줄바꿈 정리 후 255자 잘라 반환. 빈 값/`-`는 None."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text or text == "-":
        return None
    return text[:255]
