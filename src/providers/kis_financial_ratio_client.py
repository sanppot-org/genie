"""KIS 재무비율 wrapper — 결산기별 ROE/성장률/부채비율 등 추출.

HantuDomesticAPI(`financial_ratio`)를 wrap해 결산기별 행 리스트로 정규화한다.
KisIncomeStatementClient의 best-effort 패턴(네트워크 오류·rate limit retry / 그 외 전파)을 따른다.

값은 스케일 없는 % 또는 원 그대로(예: roe_val="17.07" → 17.07). 연간만 수집한다.
성장률은 음수 가능하며 적자지속/흑자전환/적자전환 등 특수값은 "0"으로 와 그대로 0.0이 된다.
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
from src.providers.kis_income_statement_client import _RATE_LIMIT_CODE, KisRateLimitError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinancialRatioRow:
    """결산기별 재무비율 1행 (스케일 없는 % 또는 원, 결측/파싱실패 → None)."""

    stac_yymm: str                  # 결산년월 YYYYMM
    roe: float | None               # ROE(%)
    debt_ratio: float | None        # 부채비율(%)
    reserve_rate: float | None      # 유보비율(%)
    revenue_growth: float | None    # 매출액 증가율(%)
    op_growth: float | None         # 영업이익 증가율(%)
    net_growth: float | None        # 순이익 증가율(%)
    eps: float | None               # EPS(원)
    bps: float | None               # BPS(원)
    sps: float | None               # 주당매출액(원)


def _parse(raw: str | None) -> float | None:
    """KIS 비율/금액 문자열 → float. 빈값/파싱 실패는 None."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


class KisFinancialRatioClient:
    """KIS 재무비율 client."""

    def __init__(self, api: HantuDomesticAPI) -> None:
        self._api = api

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, KisRateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch(self, ticker: str) -> list[FinancialRatioRow]:
        """종목 재무비율(연간) 조회.

        - 일시 네트워크 오류(RequestException) / 초당 거래건수 초과(EGW00201)는 재시도.
        - 그 외 KIS API 오류(rt_cd != 0, 잘못된 종목코드 등)는 **전파** → 호출자(sync)가
          `api_calls_failed`로 집계(빈 응답과 구분). 빈 리스트는 '정상이나 데이터 없음'만 의미.
        - stac_yymm 없는 행은 skip.
        """
        try:
            response = self._api.financial_ratio(ticker)
        except requests.RequestException:
            raise
        except Exception as e:
            if _RATE_LIMIT_CODE in str(e):
                raise KisRateLimitError(str(e)) from e
            raise

        rows: list[FinancialRatioRow] = []
        for out in response.output:
            if not out.stac_yymm:
                continue
            rows.append(FinancialRatioRow(
                stac_yymm=out.stac_yymm,
                roe=_parse(out.roe_val),
                debt_ratio=_parse(out.lblt_rate),
                reserve_rate=_parse(out.rsrv_rate),
                revenue_growth=_parse(out.grs),
                op_growth=_parse(out.bsop_prfi_inrt),
                net_growth=_parse(out.ntin_inrt),
                eps=_parse(out.eps),
                bps=_parse(out.bps),
                sps=_parse(out.sps),
            ))
        return rows
