"""데이터 조회 유틸리티 모듈"""

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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    reraise=True,
)
def fetch_yfinance(ticker: str, period: str = '1d') -> pd.DataFrame:
    """yfinance로 환율 데이터 조회 (재시도 로직 포함)

    Args:
        period:
        ticker: 환율 티커 심볼 (예: 'KRW=X')

    Returns:
        최신 환율 값
    """
    return yf.Ticker(ticker).history(period=period)
