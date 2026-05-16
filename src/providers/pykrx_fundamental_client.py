"""pykrx를 통한 일자별 종목 펀더멘털(BPS/PER/PBR/EPS/DIV/DPS) 조회 래퍼."""

from dataclasses import dataclass
from datetime import date
import logging
import math

import pandas as pd
from pykrx import stock
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.providers.pykrx_ticker_client import EmptyPykrxResponseError, _to_yyyymmdd

logger = logging.getLogger(__name__)


class KrxClosedDayError(RuntimeError):
    """휴장일 패턴 감지 — pykrx가 row를 내려주지만 모든 BPS가 0/NaN.

    재시도해도 동일 응답이므로 retry 대상에서 제외하고 즉시 raise.
    호출자는 silent skip 처리 (Slack 알림 X).
    """


@dataclass(frozen=True)
class PykrxFundamentalSnapshot:
    """pykrx 일자별 종목 펀더멘털 스냅샷. 적자/빈 셀은 None."""

    ticker: str
    bps: float | None
    per: float | None
    pbr: float | None
    eps: float | None
    div: float | None
    dps: float | None


class PykrxFundamentalClient:
    """pykrx `stock.get_market_fundamental(date, market='ALL')` 래퍼.

    - 일자 1회 호출로 전 종목(KOSPI+KOSDAQ+ETF) 스냅샷 반환
    - 빈 응답: 외부 장애로 간주 → `EmptyPykrxResponseError` 재시도
    - 휴장일(모든 BPS=0): `KrxClosedDayError`, 재시도 안 함
    - NaN은 None으로 치환 (적자 종목 PER 등)
    - ETF/ETN 필터링은 서비스 계층에서 (KR_STOCK ticker 매핑으로 자연 제외)
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, min=10, max=60),
        retry=retry_if_exception_type(EmptyPykrxResponseError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_by_date(self, base_date: date | None = None) -> list[PykrxFundamentalSnapshot]:
        """base_date=None이면 pykrx가 인접 영업일로 폴백."""
        yyyymmdd = _to_yyyymmdd(base_date)
        df = stock.get_market_fundamental(yyyymmdd, market="ALL")
        if df is None or df.empty:
            raise EmptyPykrxResponseError(
                "pykrx get_market_fundamental returned empty — possible KRX outage"
            )
        bps_max = df["BPS"].max()
        if pd.isna(bps_max) or bps_max == 0:
            # 휴장일에 pykrx는 row를 내려주지만 모든 값이 0. BPS는 회사 청산가치라
            # 정상 거래일에는 항상 양수 → 전체 0/NaN이면 휴장일로 확정.
            raise KrxClosedDayError(
                f"휴장일 추정 (전체 BPS=0/NaN), date={yyyymmdd}"
            )
        return [
            PykrxFundamentalSnapshot(
                ticker=str(idx),
                bps=_nan_to_none(row["BPS"]),
                per=_nan_to_none(row["PER"]),
                pbr=_nan_to_none(row["PBR"]),
                eps=_nan_to_none(row["EPS"]),
                div=_nan_to_none(row["DIV"]),
                dps=_nan_to_none(row["DPS"]),
            )
            for idx, row in df.iterrows()
        ]


def _nan_to_none(value: object) -> float | None:
    """pandas DataFrame 셀(NaN 가능)을 float | None으로 정규화."""
    if value is None:
        return None
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f
