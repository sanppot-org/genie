"""
업비트 API 연동 모듈

업비트 거래소와 연동하여 잔고 조회, 시세 조회, 거래 등의 기능을 제공합니다.
"""

import logging
import time
from enum import Enum

import pandas as pd
import pyupbit  # type: ignore
from pandera.typing import DataFrame

from src import constants
from src.config import UpbitConfig
from src.upbit.model.balance import BalanceInfo
from src.upbit.model.candle import CandleSchema
from src.upbit.model.error import OrderTimeoutError, UpbitAPIError
from src.upbit.model.order import OrderResult, OrderState

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


class UpbitAPI:
    @staticmethod
    def get_current_price(ticker: str = constants.KRW_BTC) -> float:
        """
        현재가 조회

        Args:
            ticker: 티커 코드 (기본값: 'KRW-BTC')

        Returns:
            현재가, 실패 시 0.0
        """
        return pyupbit.get_current_price(ticker) or 0.0

    @staticmethod
    def get_candles(ticker: str = constants.KRW_BTC, interval: CandleInterval = CandleInterval.MINUTE_60, count: int = 24) -> DataFrame[CandleSchema]:
        """
        캔들 데이터 조회

        Args:
            ticker: 티커 코드 (기본값: 'KRW-BTC')
            interval: 캔들 간격 (기본값: CandleInterval.HOUR)
            count: 조회할 캔들 개수 (기본값: 24)

        Returns:
            CandleSchema를 따르는 DataFrame, 실패 시 빈 DataFrame
        """
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval.value, count=count)

            if df is None or df.empty:
                return pd.DataFrame()

            return CandleSchema.validate(df)
        except Exception:
            logger.exception(f"캔들 데이터 조회 실패: ticker={ticker}, interval={interval.value}, count={count}")
            return pd.DataFrame()

    def __init__(self, config: UpbitConfig | None = None) -> None:
        if config is None:
            config = UpbitConfig()
        self.upbit = pyupbit.Upbit(config.upbit_access_key, config.upbit_secret_key)

    def get_available_amount(self, ticker: str = constants.CURRENCY_KRW) -> float:
        """
        특정 통화의 사용 가능 수량 조회

        Args:
            ticker: 티커 ('KRW-BTC') 또는 통화 코드 ('KRW', 'BTC')

        Returns:
            사용 가능 수량, 실패 시 0.0
        """
        return self.upbit.get_balance(ticker) or 0.0

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

    def buy_market_order(self, ticker: str, amount: float) -> OrderResult:
        """
        시장가 매수 주문

        Args:
            ticker: 마켓 ID
            amount: 주문 금액 (ticker를 얼마나 살건지 - 절대 금액)

        Returns:
            주문 결과

        Raises:
            ValueError: amount가 0 이하인 경우
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        if amount <= 0:
            raise ValueError("amount는 0보다 커야 합니다")

        result = self.upbit.buy_market_order(ticker, amount)
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
            ValueError: volume이 0 이하인 경우
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        if volume <= 0:
            raise ValueError("volume은 0보다 커야 합니다")

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
            ValueError: price가 0 이하이거나 현재가가 0이거나 조회 실패 시
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        if price <= 0:
            raise ValueError("price는 0보다 커야 합니다")

        current_price = UpbitAPI.get_current_price(ticker)

        if current_price == 0.0:
            raise ValueError(f"현재가를 조회할 수 없습니다: {ticker}")

        volume = price / current_price

        return self.sell_market_order(ticker, volume)

    def sell_all(self, ticker: str) -> OrderResult | None:
        """
        보유 중인 특정 티커를 전량 매도

        Args:
            ticker: 마켓 ID (예: 'KRW-BTC')

        Returns:
            주문 결과. 보유 수량이 없으면 None

        Raises:
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        # 보유 수량 조회
        volume = self.get_available_amount(ticker)

        if volume == 0.0:
            return None

        return self.sell_market_order(ticker, volume)

    def wait_for_order_completion(self, uuid: str, timeout: float = 30.0, poll_interval: float = 0.5) -> OrderResult:
        """
        주문 완료를 대기하고 체결 내역을 반환

        주문이 완료(done) 상태가 될 때까지 폴링하며 대기합니다.

        Args:
            uuid: 주문 고유 ID
            timeout: 최대 대기 시간(초). 기본값: 30초
            poll_interval: 폴링 간격(초). 기본값: 0.5초

        Returns:
            완료된 주문의 OrderResult

        Raises:
            OrderCancelledError: 주문이 취소된 경우
            OrderTimeoutError: 타임아웃 시간을 초과한 경우
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        start_time = time.time()

        while True:
            # 주문 상태 조회
            result = self.upbit.get_order(uuid)
            self._check_api_error(result)

            order_result = OrderResult.from_dict(result)

            # 주문 완료 확인
            if order_result.state == OrderState.DONE or order_result.state == OrderState.CANCEL:
                logger.debug(f"주문 체결 완료: {uuid}")
                return order_result

            # 타임아웃 확인
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.error(f"주문 완료 대기 타임아웃: {uuid} ({elapsed:.2f}초)")
                raise OrderTimeoutError(uuid, timeout)

            # 다음 폴링까지 대기
            time.sleep(poll_interval)

    def buy_market_order_and_wait(self, ticker: str, amount: float, timeout: float = 30.0) -> OrderResult:
        """
        시장가 매수 주문 후 체결 완료까지 대기

        Args:
            ticker: 마켓 ID
            amount: 주문 금액 (ticker를 얼마나 살건지 - 절대 금액)
            timeout: 최대 대기 시간(초). 기본값: 30초

        Returns:
            완료된 주문의 OrderResult

        Raises:
            ValueError: amount가 0 이하인 경우
            OrderCancelledError: 주문이 취소된 경우
            OrderTimeoutError: 타임아웃 시간을 초과한 경우
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        order_result = self.buy_market_order(ticker, amount)
        return self.wait_for_order_completion(order_result.uuid, timeout)

    def sell_market_order_and_wait(self, ticker: str, volume: float, timeout: float = 30.0) -> OrderResult:
        """
        시장가 매도 주문 후 체결 완료까지 대기

        Args:
            ticker: 마켓 ID
            volume: 주문 수량 (내가 가진 수량)
            timeout: 최대 대기 시간(초). 기본값: 30초

        Returns:
            완료된 주문의 OrderResult

        Raises:
            ValueError: volume이 0 이하인 경우
            OrderCancelledError: 주문이 취소된 경우
            OrderTimeoutError: 타임아웃 시간을 초과한 경우
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        order_result = self.sell_market_order(ticker, volume)
        return self.wait_for_order_completion(order_result.uuid, timeout)

    def sell_market_order_by_price_and_wait(self, ticker: str, price: float, timeout: float = 30.0) -> OrderResult:
        """
        KRW 금액 기반 시장가 매도 주문 후 체결 완료까지 대기

        Args:
            ticker: 마켓 ID (예: 'KRW-BTC')
            price: 매도할 금액 (KRW)
            timeout: 최대 대기 시간(초). 기본값: 30초

        Returns:
            완료된 주문의 OrderResult

        Raises:
            ValueError: price가 0 이하이거나 현재가가 0이거나 조회 실패 시
            OrderCancelledError: 주문이 취소된 경우
            OrderTimeoutError: 타임아웃 시간을 초과한 경우
            UpbitAPIError: API 호출 중 에러가 발생한 경우
        """
        order_result = self.sell_market_order_by_price(ticker, price)
        return self.wait_for_order_completion(order_result.uuid, timeout)

    @staticmethod
    def _check_api_error(result: dict | list | None) -> None:
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

        if isinstance(result, dict) and "error" in result:
            raise UpbitAPIError(result["error"])
