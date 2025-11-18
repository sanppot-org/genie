"""데이터 조회 유틸리티 모듈"""
from datetime import datetime
from enum import Enum

import FinanceDataReader as fdr  # noqa: N813
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed
import yfinance as yf


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    reraise=True,
)
def fetch_finance_data_reader(ticker: str) -> pd.DataFrame:
    """FinanceDataReader로 가격 데이터 조회 (재시도 로직 포함)

    Args:
        ticker: 티커 심볼

    Returns:
        가격 데이터 DataFrame
    """
    return fdr.DataReader(ticker)


class YfPeriod(Enum):
    ONE_DAY = '1d'
    FIVE_DAYS = '5d'
    ONE_MONTH = '1mo'
    THREE_MONTHS = '3mo'
    SIX_MONTHS = '6mo'
    ONE_YEAR = '1y'
    TWO_YEARS = '2y'
    FIVE_YEARS = '5y'
    TEN_YEARS = '10y'
    YTD = 'ytd'
    MAX = 'max'


class YfInterval(Enum):
    ONE_MINUTE = '1m'
    TWO_MINUTES = '2m'
    FIVE_MINUTES = '5m'
    FIFTEEN_MINUTES = '15m'
    THIRTY_MINUTES = '30m'
    SIXTY_MINUTES = '60m'
    NINETY_MINUTES = '90m'
    ONE_HOUR = '1h'
    ONE_DAY = '1d'
    FIVE_DAYS = '5d'
    ONE_WEEK = '1wk'
    ONE_MONTH = '1mo'
    THREE_MONTHS = '3mo'


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    reraise=True,
)
def fetch_yfinance(
        ticker: str,
        period: YfPeriod | None = None,
        interval: YfInterval = YfInterval.ONE_DAY,
        start_date: datetime | None = None,
        end_date: datetime | None = None
) -> pd.DataFrame:
    """yfinance로 환율 데이터 조회 (재시도 로직 포함)

    Args:
        ticker: 환율 티커 심볼 (예: 'KRW=X')
        period: 기간
        interval: 간격
        start_date: 시작일
        end_date: 종료일

    Returns:
        최신 환율 값
    """
    return yf.Ticker(ticker).history(
        period=period.value if period else None,
        interval=interval.value if interval else None,
        start=start_date.strftime("%Y-%m-%d") if start_date else None,
        end=end_date.strftime("%Y-%m-%d") if end_date else None
    )
