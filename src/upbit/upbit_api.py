"""
업비트 API 연동 모듈

업비트 거래소와 연동하여 잔고 조회, 시세 조회, 거래 등의 기능을 제공합니다.
"""

import logging
from enum import Enum

import pyupbit
from pandas import DataFrame

from src import constants as const
from src.config import UpbitConfig
from src.upbit.model.balance import BalanceInfo
from src.upbit.model.candle import CandleData
from src.upbit.model.error import UpbitAPIError
from src.upbit.model.order import OrderResult

logger = logging.getLogger(__name__)


class CandleInterval(Enum):
    """캔들 간격"""
    DAY = "day"
    MINUTE_1 = "minute1"
    MINUTE_3 = "minute3"
    MINUTE_5 = "minute5"
    MINUTE_10 = "minute10"
    MINUTE_15 = "minute15"
    MINUTE_30 = "minute30"
    MINUTE_60 = "minute60"
    MINUTE_240 = "minute240"
    WEEK = "week"
    MONTH = "month"


def get_current_price(ticker: str = const.KRW_BTC) -> float:
    """
    현재가 조회

    Args:
        ticker: 티커 코드 (기본값: 'KRW-BTC')

    Returns:
        현재가, 실패 시 0.0
    """
    return pyupbit.get_current_price(ticker) or 0.0


def get_candles(
        ticker: str = const.KRW_BTC,
        interval: CandleInterval = CandleInterval.MINUTE_60,
        count: int = 24
) -> list[CandleData]:
    """
    캔들 데이터 조회

    Args:
        ticker: 티커 코드 (기본값: 'KRW-BTC')
        interval: 캔들 간격 (기본값: CandleInterval.HOUR)
        count: 조회할 캔들 개수 (기본값: 24)

    Returns:
        CandleData 리스트, 실패 시 빈 리스트
    """
    try:
        df: DataFrame = pyupbit.get_ohlcv(ticker, interval=interval.value, count=count)

        if df is None or df.empty:
            return []

        return [CandleData.from_dataframe_row(row) for _, row in df.iterrows()]
    except Exception:
        logger.exception(f"캔들 데이터 조회 실패: ticker={ticker}, interval={interval.value}, count={count}")
        return []


class UpbitAPI:
    def __init__(self, config: UpbitConfig):
        self.upbit = pyupbit.Upbit(config.upbit_access_key, config.upbit_secret_key)

    def get_balance(self, currency: str = const.CURRENCY_KRW) -> float:
        """
        특정 통화의 사용 가능 수량 조회

        Args:
            currency: 통화 코드 (기본값: 'KRW')

        Returns:
            사용 가능 수량, 실패 시 0.0
        """
        return self.upbit.get_balance(currency) or 0.0

    def get_balances(self) -> list[BalanceInfo]:
        """
        전체 계좌 잔고 조회

        Returns:
            모든 보유 자산의 잔고 정보 리스트

        Raises:
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        balances = self.upbit.get_balances()
        self._check_api_error(balances)

        return [BalanceInfo.from_dict(balance) for balance in balances] if balances else []

    def buy_market_order(self, ticker: str, price: float) -> OrderResult:
        """
        시장가 매수 주문

        Args:
            ticker: 마켓 ID
            price: 주문 금액 (ticker를 얼마나 살건지 - 절대 금액)

        Returns:
            주문 결과

        Raises:
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        result = self.upbit.buy_market_order(ticker, price)
        self._check_api_error(result)
        return OrderResult.from_dict(result)

    def sell_market_order(self, ticker: str, volume: float) -> OrderResult:
        """
        시장가 매도 주문

        Args:
            ticker: 마켓 ID
            volume: 주문 수량 (내가 가진 수량)

        Returns:
            주문 결과

        Raises:
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        result = self.upbit.sell_market_order(ticker, volume)
        self._check_api_error(result)
        return OrderResult.from_dict(result)

    def sell_market_order_by_price(self, ticker: str, price: float) -> OrderResult:
        """
        KRW 금액 기반 시장가 매도 주문

        Args:
            ticker: 마켓 ID (예: 'KRW-BTC')
            price: 매도할 금액 (KRW)

        Returns:
            주문 결과

        Raises:
            ValueError: 현재가가 0이거나 조회 실패 시
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        current_price = get_current_price(ticker)

        if current_price == 0.0:
            raise ValueError(f"현재가를 조회할 수 없습니다: {ticker}")

        volume = price / current_price
        return self.sell_market_order(ticker, volume)

    @staticmethod
    def _check_api_error(result: dict | list | None):
        """
        API 응답에서 에러 확인 및 예외 발생

        Args:
            result: API 응답 결과

        Raises:
            UpbitAPIError: 응답에 에러가 포함된 경우 또는 응답이 None인 경우
        """
        if result is None:
            raise UpbitAPIError.empty_response()

        logger.debug(f"api response: {result}")

        if isinstance(result, dict) and 'error' in result:
            raise UpbitAPIError(result['error'])
