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
import re

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


@dataclass(frozen=True)
class CancellationEvent:
    """DART 주식소각결정 공시(자사주 소각)에서 추출한 이벤트."""

    stock_code: str
    rcept_no: str
    report_nm: str
    resolution_date: date     # 이사회결의일(결정일)
    cancel_date: date | None  # 소각 예정일
    common_shares: int | None
    preferred_shares: int | None
    cancel_amount: int | None
    acquisition_method: str | None


# DART event() 키워드 → 이벤트 타입 라벨
_BUYBACK_KEYWORD_MAP: tuple[tuple[str, str], ...] = (
    ("자기주식취득", "ACQUISITION"),
    ("자기주식처분", "DISPOSAL"),
)

# 주식소각결정 공시명 판별 키워드 ("[기재정정] 주식소각결정", "(자회사의 주요경영사항) 주식소각결정" 변형 포함).
_CANCELLATION_REPORT_KEYWORD = "주식소각결정"


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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_cancellation_events(
            self, stock_code: str, from_date: date, to_date: date,
    ) -> list[CancellationEvent]:
        """주식소각결정 공시(자사주 소각) 일괄 조회.

        `list()`로 접수일 범위 공시 목록을 받아 "주식소각결정" 공시만 필터한 뒤,
        각 접수번호의 원문(document)을 파싱해 소각 수량·금액·예정일을 추출한다.

        Args:
            stock_code: 종목코드 (예: '005930')
            from_date: 시작 접수일 (포함)
            to_date: 종료 접수일 (포함)

        Returns:
            소각 이벤트 리스트. corp_code 매핑 실패 / 응답 없음은 빈 리스트.
            필수필드(이사회결의일) 누락 행은 warning 후 skip(silent loss 방지).
        """
        start = from_date.strftime("%Y-%m-%d")
        end = to_date.strftime("%Y-%m-%d")

        try:
            df = self._reader.list(stock_code, start, end)
        except ValueError:
            # corp_code 매핑 실패 — 신규 상장 직후 등
            return []

        if df is None or df.empty:
            return []

        results: list[CancellationEvent] = []
        for _, row in df.iterrows():
            report_nm = str(row.get("report_nm") or "").strip()
            if _CANCELLATION_REPORT_KEYWORD not in report_nm:
                continue

            # 자회사 공시 배제: list() 결과의 stock_code가 대상과 다르면 제외.
            row_stock_code = str(row.get("stock_code") or "").strip()
            if row_stock_code and row_stock_code != stock_code:
                continue

            rcept_no = str(row.get("rcept_no") or "").strip()
            if not rcept_no:
                continue

            doc = self._reader.document(rcept_no)
            parsed = _parse_cancellation_document(doc)
            if parsed is None or parsed.get("resolution_date") is None:
                logger.warning(
                    "주식소각결정 문서 파싱 실패 stock_code=%s rcept_no=%s report_nm=%s",
                    stock_code, rcept_no, report_nm,
                )
                continue

            results.append(CancellationEvent(
                stock_code=stock_code,
                rcept_no=rcept_no,
                report_nm=report_nm[:128],
                resolution_date=parsed["resolution_date"],
                cancel_date=parsed.get("cancel_date"),
                common_shares=parsed.get("common_shares"),
                preferred_shares=parsed.get("preferred_shares"),
                cancel_amount=parsed.get("cancel_amount"),
                acquisition_method=parsed.get("acquisition_method"),
            ))

        return results


def _parse_cancellation_document(doc: str) -> dict | None:
    """주식소각결정 공시 원문(HTML)에서 소각 수량·금액·예정일·결의일 추출.

    resolution_date(이사회결의일)가 없으면 None 반환(파싱 실패). 나머지는 None 허용.
    """
    if not doc:
        return None

    text = re.sub(r"<[^>]+>", " ", doc)
    text = re.sub(r"\s+", " ", text)

    result: dict = {}

    # 소각 수량: "소각할 주식의 종류와 수" ~ "발행주식 총수" 구간에서만 추출
    # (발행주식총수의 보통주/종류주와 혼동 방지).
    section_match = re.search(
        r"소각할 주식의 종류와 수(.*?)발행주식\s*총수", text
    )
    if section_match:
        section = section_match.group(1)
        common_match = re.search(r"보통주식\s*\(주\)\s*([\d,]+)", section)
        preferred_match = re.search(r"종류주식\s*\(주\)\s*([\d,]+)", section)
        result["common_shares"] = _parse_int(common_match.group(1)) if common_match else None
        result["preferred_shares"] = _parse_int(preferred_match.group(1)) if preferred_match else None

    amount_match = re.search(r"소각예정금액\(원\)\s*([\d,-]+)", text)
    if amount_match:
        result["cancel_amount"] = _parse_int(amount_match.group(1))

    method_match = re.search(r"소각할 주식의 취득방법\s*(.+?)\s*\d+\.", text)
    if method_match:
        method = _normalize_text(method_match.group(1))
        result["acquisition_method"] = method[:64] if method else None  # 컬럼 String(64) 정합

    cancel_date_match = re.search(r"소각\s*예정일\s*(\d{4}-\d{2}-\d{2})", text)
    if cancel_date_match:
        result["cancel_date"] = _parse_dart_date(cancel_date_match.group(1))

    # "이사회결의일(결정일)"(삼성 양식) / "이사회결의일"(다수 종목 양식) 모두 허용.
    resolution_match = re.search(r"이사회결의일\s*(?:\(결정일\))?\s*(\d{4}-\d{2}-\d{2})", text)
    result["resolution_date"] = _parse_dart_date(resolution_match.group(1)) if resolution_match else None

    if result["resolution_date"] is None:
        return None

    return result


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
