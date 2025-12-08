"""
업비트 API 연동 모듈

업비트 거래소와 연동하여 잔고 조회, 시세 조회, 거래 등의 기능을 제공합니다.
"""

from datetime import datetime
from enum import Enum
import hashlib
import logging
import time
from urllib.parse import unquote, urlencode
import uuid

import jwt
import pandas as pd
from pandera.typing import DataFrame
import pyupbit  # type: ignore

from src import constants
from src.common.http_client import HTTPMethod, make_api_request
from src.config import UpbitConfig
from src.upbit.model.balance import BalanceInfo
from src.upbit.model.candle import CandleSchema
from src.upbit.model.error import OrderTimeoutError, UpbitAPIError
from src.upbit.model.order import OrderParams, OrderResult, OrderSide, OrderState, OrderType, TimeInForce

logger = logging.getLogger(__name__)


class UpbitCandleInterval(Enum):
    """캔들 간격 (값, API 엔드포인트)"""

    DAY = ("day", "/v1/candles/days")
    MINUTE_1 = ("minute1", "/v1/candles/minutes/1")
    MINUTE_3 = ("minute3", "/v1/candles/minutes/3")
    MINUTE_5 = ("minute5", "/v1/candles/minutes/5")
    MINUTE_10 = ("minute10", "/v1/candles/minutes/10")
    MINUTE_15 = ("minute15", "/v1/candles/minutes/15")
    MINUTE_30 = ("minute30", "/v1/candles/minutes/30")
    MINUTE_60 = ("minute60", "/v1/candles/minutes/60")
    MINUTE_240 = ("minute240", "/v1/candles/minutes/240")
    WEEK = ("week", "/v1/candles/weeks")
    MONTH = ("month", "/v1/candles/months")

    @property
    def interval_name(self) -> str:
        """pyupbit 호환을 위한 간격 이름"""
        return self.value[0]

    @property
    def endpoint(self) -> str:
        """Upbit API 엔드포인트"""
        return self.value[1]


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

    def __init__(self, config: UpbitConfig | None = None) -> None:
        if config is None:
            config = UpbitConfig()
        self.config = config
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

        result = self.upbit.buy_market_order(ticker, amount)  # FIXME: 에러 로그가 제대로 안 보여서 불편하다.
        logger.info(f"ticker={ticker}, amount={amount} 매수 주문 결과: {result}")
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
        logger.info(f"ticker={ticker}, volume={volume} 매도 주문 결과: {result}")
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
        return self._wait_for_order_completion(order_result.uuid, timeout)

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
        return self._wait_for_order_completion(order_result.uuid, timeout)

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
        return self._wait_for_order_completion(order_result.uuid, timeout)

    def _wait_for_order_completion(self, uuid: str, timeout: float = 30.0, poll_interval: float = 0.5) -> OrderResult:
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
                logger.info(f"주문 체결 완료: {uuid}")
                return order_result

            # 타임아웃 확인
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.error(f"주문 완료 대기 타임아웃: {uuid} ({elapsed:.2f}초)")
                raise OrderTimeoutError(uuid, timeout)

            # 다음 폴링까지 대기
            time.sleep(poll_interval)

    def place_order(
            self,
            market: str,
            side: OrderSide,
            ord_type: OrderType,
            time_in_force: TimeInForce | None = None,
            volume: float | None = None,
            price: float | None = None,
    ) -> OrderResult:
        """
        주문 실행 (지정가/시장가/최유리지정가 모두 지원)

        Args:
            market: 마켓 ID (예: 'KRW-BTC')
            side: 'bid' (매수) 또는 'ask' (매도)
            ord_type: 'limit' (지정가), 'price' (시장가 매수), 'market' (시장가 매도), 'best' (최유리지정가)
            time_in_force: 주문 실행 조건 (선택, 최유리지정가 시 필수)
            volume: 주문량 (양수 float)
            price: 주문 가격 (양수 float)

        Returns:
            주문 결과

        Raises:
            ValidationError: 파라미터 유효성 검사 실패 시
            UpbitAPIError: API 호출 중 에러 발생 시
        """
        path = "/v1/orders"

        order_params = OrderParams(
            market=market,
            side=side,
            ord_type=ord_type,
            time_in_force=time_in_force,
            volume=volume,
            price=price,
        )

        params = order_params.to_dict()

        headers = {
            "Authorization": f"Bearer {self._generate_jwt_token(params)}",
            "Accept": "application/json",
        }

        response = make_api_request(f"{self.config.base_url}{path}", HTTPMethod.POST, headers=headers, json=params)
        result = response.json()

        logger.info(f"주문 실행 결과: {result}")
        self._check_api_error(result)

        return OrderResult.from_dict(result)

    def buy_best_fok_order(self, market: str, amount: float) -> OrderResult:
        """
        최유리 FOK 매수 주문

        Fill or Kill 조건으로 최유리 가격에 매수 주문을 넣습니다.
        지정한 금액만큼 즉시 체결되지 않으면 주문이 취소됩니다.

        Args:
            market: 마켓 ID (예: 'KRW-BTC')
            amount: 주문 금액 (양수 float)

        Returns:
            주문 결과

        Raises:
            ValueError: price가 0 이하인 경우
            ValidationError: 파라미터 유효성 검사 실패 시
            UpbitAPIError: API 호출 중 에러 발생 시
        """
        if amount <= 0:
            raise ValueError("price는 0보다 커야 합니다")

        return self.place_order(
            market=market,
            side=OrderSide.BID,
            ord_type=OrderType.BEST,
            time_in_force=TimeInForce.FOK,
            price=amount
        )

    def sell_best_ioc_order(self, market: str, volume: float) -> OrderResult:
        """
        최유리 IOC 매도 주문

        Immediate or Cancel 조건으로 최유리 가격에 매도 주문을 넣습니다.
        즉시 체결 가능한 수량만큼만 체결되고, 나머지는 취소됩니다.

        Args:
            market: 마켓 ID (예: 'KRW-BTC')
            volume: 주문 수량 (양수 float)

        Returns:
            주문 결과

        Raises:
            ValueError: volume이 0 이하인 경우
            ValidationError: 파라미터 유효성 검사 실패 시
            UpbitAPIError: API 호출 중 에러 발생 시
        """
        if volume <= 0:
            raise ValueError("volume은 0보다 커야 합니다")

        return self.place_order(
            market=market,
            side=OrderSide.ASK,
            ord_type=OrderType.BEST,
            time_in_force=TimeInForce.IOC,
            volume=volume
        )

    def buy_best_fok_order_and_wait(
            self,
            market: str,
            amount: float,
            timeout: float = 30.0
    ) -> OrderResult:
        """
        최유리 FOK 매수 주문 후 체결 완료까지 대기

        Fill or Kill이므로:
        - 성공: state = DONE, executed_volume > 0
        - 실패: state = CANCEL, executed_volume = 0

        Args:
            market: 마켓 ID (예: 'KRW-BTC')
            amount: 주문 금액 (원화)
            timeout: 최대 대기 시간(초). 기본값: 30초

        Returns:
            완료된 주문의 OrderResult

        Raises:
            OrderCancelledError: FOK 조건 미충족으로 주문 취소
            OrderTimeoutError: 타임아웃 초과
            UpbitAPIError: API 호출 오류
        """
        order_result = self.buy_best_fok_order(market, amount)
        return self._wait_for_order_completion(order_result.uuid, timeout)

    def sell_best_ioc_order_and_wait(
            self,
            market: str,
            volume: float,
            timeout: float = 30.0
    ) -> OrderResult:
        """
        최유리 IOC 매도 주문 후 체결 완료까지 대기

        Immediate or Cancel이므로:
        - 항상 state = DONE
        - executed_volume은 즉시 체결 가능한 만큼

        Args:
            market: 마켓 ID (예: 'KRW-BTC')
            volume: 주문 수량
            timeout: 최대 대기 시간(초). 기본값: 30초

        Returns:
            완료된 주문의 OrderResult

        Raises:
            OrderTimeoutError: 타임아웃 초과
            UpbitAPIError: API 호출 오류
        """
        order_result = self.sell_best_ioc_order(market, volume)
        return self._wait_for_order_completion(order_result.uuid, timeout)

    def _generate_jwt_token(self, params: dict) -> str:
        """
        주문 파라미터로부터 JWT 토큰 생성

        Args:
            params: 주문 파라미터 딕셔너리

        Returns:
            생성된 JWT 토큰
        """
        query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
        m = hashlib.sha512()
        m.update(query_string)
        query_hash = m.hexdigest()

        payload = {
            "access_key": self.config.upbit_access_key,
            "nonce": str(uuid.uuid4()),
            "query_hash": query_hash,
            "query_hash_alg": "SHA512",
        }

        return jwt.encode(payload, self.config.upbit_secret_key, algorithm="HS256")

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

        logger.info(f"api response: {result}")

        if isinstance(result, dict) and "error" in result:
            raise UpbitAPIError(result["error"])

    @staticmethod
    def _response_to_dataframe(response_data: list) -> pd.DataFrame:
        """
        Upbit API 응답을 CandleSchema 형식의 DataFrame으로 변환

        Args:
            response_data: Upbit API 응답 데이터 (리스트)

        Returns:
            CandleSchema 컬럼을 가진 DataFrame
        """
        if not response_data:
            return pd.DataFrame()

        df = pd.DataFrame(response_data)

        column_mapping = {
            "opening_price": "open",
            "high_price": "high",
            "low_price": "low",
            "trade_price": "close",
            "candle_acc_trade_volume": "volume",
            "candle_acc_trade_price": "value",
            "candle_date_time_utc": "index",
            "candle_date_time_kst": "localtime",
        }

        # 컬럼명 변경
        df = df.rename(columns=column_mapping)

        df["index"] = pd.to_datetime(df["index"], utc=True)
        df = df.set_index("index")

        df["localtime"] = pd.to_datetime(df["localtime"])

        # 필요한 컬럼만 선택
        df = df[["localtime", "open", "high", "low", "close", "volume", "value"]]

        return df

    def get_candles(
            self,
            market: str,
            interval: UpbitCandleInterval = UpbitCandleInterval.DAY,
            count: int = 1,
            to: datetime | None = None,
    ) -> DataFrame[CandleSchema]:
        """
        캔들 데이터 조회

        Args:
            market: 마켓 ID (예: 'KRW-BTC')
            interval: 조회할 캔들 간격 (예: UpbitCandleInterval.DAY)
            count: 조회할 캔들 개수 (기본값: 1, 제한 없음)
            to: 특정 시점 이전 데이터만 조회 (선택)

        Returns:
            CandleSchema를 따르는 DataFrame

        Raises:
            ValueError: count가 0 이하이거나 market이 비어있는 경우
            UpbitAPIError: API 호출 중 에러가 발생한 경우

        Examples:
            >>> api = UpbitAPI()
            >>> # 100개 조회
            >>> daily_candles = api.get_candles(
            ...     market='KRW-BTC',
            ...     interval=UpbitCandleInterval.DAY,
            ...     count=100
            ... )
            >>> # 500개 조회 (내부적으로 3번 호출)
            >>> many_candles = api.get_candles(
            ...     market='KRW-BTC',
            ...     interval=UpbitCandleInterval.MINUTE_60,
            ...     count=500
            ... )
        """
        if not market or not market.strip():
            raise ValueError("market은 비어있을 수 없습니다")
        if count <= 0:
            raise ValueError("count는 1 이상이어야 합니다")

        try:
            # count가 200 이하면 단일 호출
            if count <= 200:
                return self._fetch_single_candles(market, interval, count, to)

            # count가 200 초과면 반복 호출
            all_dataframes = []
            remaining = count
            current_to = to

            while remaining > 0:
                batch_count = min(remaining, 200)

                df = self._fetch_single_candles(market, interval, batch_count, current_to)

                if df.empty:
                    break

                all_dataframes.append(df)
                remaining -= len(df)

                if remaining > 0 and len(df) > 0:
                    current_to = df.index.min()
                    time.sleep(0.11)
                else:
                    break

            if not all_dataframes:
                return pd.DataFrame()  # type: ignore

            combined_df = pd.concat(all_dataframes)
            # 중복 제거 및 시간순 정렬 (과거 -> 최신)
            combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
            combined_df = combined_df.sort_index(ascending=True)

            result_df = combined_df.head(count)

            return CandleSchema.validate(result_df)

        except Exception as e:
            logger.error(f"캔들 데이터 조회 실패: market={market}, interval={interval}, count={count}, error={e}")
            return pd.DataFrame()  # type: ignore

    def _fetch_single_candles(
            self,
            market: str,
            interval: UpbitCandleInterval,
            count: int,
            to: datetime | None = None,
    ) -> DataFrame[CandleSchema]:
        """
        단일 API 호출로 캔들 데이터 조회 (최대 200개)

        Args:
            market: 마켓 ID
            interval: 캔들 간격
            count: 조회할 개수 (1-200)
            to: 특정 시점 이전 데이터만 조회

        Returns:
            CandleSchema DataFrame
        """
        params = {"market": market, "count": min(count, 200)}
        if to:
            params["to"] = to.strftime("%Y-%m-%d %H:%M:%S")

        response = make_api_request(
            url=f"{self.config.base_url}{interval.endpoint}",
            method=HTTPMethod.GET,
            params=params,
            headers={"accept": "application/json"},
        )

        response_data = response.json()
        self._check_api_error(response_data)

        df = self._response_to_dataframe(response_data)
        return CandleSchema.validate(df)  # type: ignore
