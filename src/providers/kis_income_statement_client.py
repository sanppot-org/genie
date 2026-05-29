"""KIS 손익계산서 wrapper — 결산기별 매출/영업이익/순이익 추출.

HantuDomesticAPI(`income_statement`)를 wrap해 결산기별 행 리스트로 정규화한다.
KisCompanyClient의 best-effort 패턴(네트워크 오류 retry / 그 외는 빈 리스트)을 따른다.

금액 단위 = 억원. KIS는 문자열("2589355.00")로 주고 적자는 음수("-1062.00"),
미제공 필드는 "99.99" sentinel → None 정규화. 분기(QUARTER)는 연단위 누적합산이다.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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

# KIS 미제공 필드 sentinel (실측). 실값과 충돌 없음(금액 억원 단위라 99.99는 비현실값).
_MISSING_SENTINEL = Decimal("99.99")

PERIOD_ANNUAL = "ANNUAL"
PERIOD_QUARTER = "QUARTER"

# period_type → KIS FID_DIV_CLS_CODE
_DIV_CLS = {PERIOD_ANNUAL: "0", PERIOD_QUARTER: "1"}

# KIS 초당 거래건수 초과(rate limit) 코드 — 일시적이므로 재시도 대상.
_RATE_LIMIT_CODE = "EGW00201"


class KisRateLimitError(Exception):
    """KIS 초당 거래건수 초과(EGW00201). 일시적 → 재시도."""


@dataclass(frozen=True)
class IncomeStatementRow:
    """결산기별 손익계산서 1행 (억원, 미제공/적자 → None/음수)."""

    stac_yymm: str          # 결산년월 YYYYMM
    period_type: str        # ANNUAL | QUARTER
    sale_account: Decimal | None    # 매출액
    sale_cost: Decimal | None       # 매출원가
    sale_totl_prfi: Decimal | None  # 매출총이익
    bsop_prti: Decimal | None       # 영업이익
    op_prfi: Decimal | None         # 경상이익
    thtr_ntin: Decimal | None       # 당기순이익


def _parse(raw: str | None) -> Decimal | None:
    """KIS 금액 문자열 → Decimal. 빈값/"99.99" sentinel/파싱 실패는 None."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        value = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    if value == _MISSING_SENTINEL:
        return None
    return value


class KisIncomeStatementClient:
    """KIS 손익계산서 client."""

    def __init__(self, api: HantuDomesticAPI) -> None:
        self._api = api

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, KisRateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch(self, ticker: str, period_type: str) -> list[IncomeStatementRow]:
        """종목 손익계산서 조회 (raw 결산기 행 그대로, 연간 선두 비결산행 필터는 조회 레이어 담당).

        - 일시 네트워크 오류(RequestException) / 초당 거래건수 초과(EGW00201)는 재시도.
        - 그 외 KIS API 오류(rt_cd != 0, 잘못된 종목코드 등)는 **전파** → 호출자(sync)가
          `api_calls_failed`로 집계(빈 응답과 구분). 빈 리스트는 '정상이나 데이터 없음'만 의미.
        - stac_yymm 없는 행은 skip
        """
        div = _DIV_CLS[period_type]
        try:
            response = self._api.income_statement(ticker, div)
        except requests.RequestException:
            raise
        except Exception as e:
            if _RATE_LIMIT_CODE in str(e):
                raise KisRateLimitError(str(e)) from e
            raise

        rows: list[IncomeStatementRow] = []
        for out in response.output:
            if not out.stac_yymm:
                continue
            rows.append(IncomeStatementRow(
                stac_yymm=out.stac_yymm,
                period_type=period_type,
                sale_account=_parse(out.sale_account),
                sale_cost=_parse(out.sale_cost),
                sale_totl_prfi=_parse(out.sale_totl_prfi),
                bsop_prti=_parse(out.bsop_prti),
                op_prfi=_parse(out.op_prfi),
                thtr_ntin=_parse(out.thtr_ntin),
            ))
        return rows
