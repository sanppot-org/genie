"""pykrx를 통한 일자별 KR 주식 OHLCV 조회 래퍼."""

from dataclasses import dataclass
from datetime import date
import logging

import pandas as pd
from pykrx import stock
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.providers.pykrx_fundamental_client import KrxClosedDayError
from src.providers.pykrx_ticker_client import EmptyPykrxResponseError, _to_yyyymmdd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PykrxDailyCandleSnapshot:
    """pykrx 일자별 종목 OHLCV 스냅샷."""

    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_value: int | None


class PykrxDailyCandleClient:
    """pykrx `stock.get_market_ohlcv(date, market='ALL')` 래퍼.

    - 일자 1회 호출로 전 종목(KOSPI+KOSDAQ+ETF) OHLCV 반환
    - 빈 응답: 외부 장애로 간주 → `EmptyPykrxResponseError` 재시도
    - 휴장일(전체 거래량=0): `KrxClosedDayError`, 재시도 안 함
    - 거래대금 컬럼은 옛 pykrx 버전에 없을 수 있음 → 조건부 추출, NaN/없음은 None
    - ETF/ETN 필터링은 서비스 계층에서 (KR_STOCK ticker 매핑으로 자연 제외)
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, min=10, max=60),
        retry=retry_if_exception_type(EmptyPykrxResponseError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_by_date(self, base_date: date) -> list[PykrxDailyCandleSnapshot]:
        """base_date의 전 종목 일봉 스냅샷."""
        yyyymmdd = _to_yyyymmdd(base_date)
        df = stock.get_market_ohlcv(yyyymmdd, market="ALL")
        if df is None or df.empty:
            raise EmptyPykrxResponseError(
                "pykrx get_market_ohlcv returned empty — possible KRX outage"
            )
        if df["거래량"].sum() == 0:
            # 휴장일에는 row가 내려와도 모든 거래량이 0.
            raise KrxClosedDayError(f"휴장일 추정 (전체 거래량=0), date={yyyymmdd}")

        has_trade_value = "거래대금" in df.columns
        return [
            PykrxDailyCandleSnapshot(
                ticker=str(idx),
                open=float(row["시가"]),
                high=float(row["고가"]),
                low=float(row["저가"]),
                close=float(row["종가"]),
                volume=int(row["거래량"]),
                trade_value=(
                    int(row["거래대금"])
                    if has_trade_value and not pd.isna(row["거래대금"])
                    else None
                ),
            )
            for idx, row in df.iterrows()
        ]
