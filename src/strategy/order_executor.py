"""주문 실행을 담당하는 모듈"""

import logging
from dataclasses import dataclass
from typing import Protocol

from src.upbit.model.order import OrderResult
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    주문 체결 결과를 나타내는 클래스

    Attributes:
        ticker: 마켓 ID (예: "KRW-BTC")
        executed_volume: 체결된 수량
        executed_price: 체결된 가격
        executed_amount: 체결된 금액 (가격 * 수량)
        order: 원본 주문 정보
    """

    ticker: str
    executed_volume: float
    executed_price: float
    executed_amount: float
    order: OrderResult


class OrderExecutorProtocol(Protocol):
    """OrderExecutor 인터페이스 (테스트용 모킹 가능)"""

    def buy(self, ticker: str, amount: float) -> ExecutionResult:
        """시장가 매수 주문 실행"""
        ...

    def sell(self, ticker: str, volume: float) -> ExecutionResult:
        """시장가 매도 주문 실행"""
        ...


class OrderExecutor:
    """주문 실행 책임만 담당하는 클래스"""

    def __init__(self, upbit_api: UpbitAPI) -> None:
        """
        OrderExecutor 초기화

        Args:
            upbit_api: UpbitAPI 인스턴스
        """
        self._upbit_api = upbit_api

    def buy(self, ticker: str, amount: float) -> ExecutionResult:
        """
        시장가 매수 주문 실행

        Args:
            ticker: 마켓 ID (예: "KRW-BTC")
            amount: 매수 금액 (원화)

        Returns:
            ExecutionResult: 체결 결과
        """
        logger.info(f"매수 주문 시작: {ticker}, 금액: {amount:,.0f}원")

        order_result = self._upbit_api.buy_market_order_and_wait(ticker, amount)
        execution_price = order_result.trades[0].price
        execution_volume = order_result.trades[0].volume

        result = ExecutionResult(
            ticker=ticker,
            executed_volume=execution_volume,
            executed_price=execution_price,
            executed_amount=amount,
            order=order_result,
        )

        logger.info(
            f"✅ 매수 완료: {ticker} | "
            f"수량: {execution_volume:.8f} | "
            f"가격: {execution_price:,.0f}원 | "
            f"금액: {amount:,.0f}원"
        )

        return result

    def sell(self, ticker: str, volume: float) -> ExecutionResult:
        """
        시장가 매도 주문 실행

        Args:
            ticker: 마켓 ID (예: "KRW-BTC")
            volume: 매도 수량

        Returns:
            ExecutionResult: 체결 결과
        """
        logger.info(f"매도 주문 시작: {ticker}, 수량: {volume:.8f}")

        order_result = self._upbit_api.sell_market_order_and_wait(ticker, volume)
        execution_price = order_result.trades[0].price
        execution_volume = order_result.trades[0].volume
        amount = execution_price * execution_volume

        result = ExecutionResult(
            ticker=ticker,
            executed_volume=execution_volume,
            executed_price=execution_price,
            executed_amount=amount,
            order=order_result,
        )

        logger.info(
            f"✅ 매도 완료: {ticker} | "
            f"수량: {execution_volume:.8f} | "
            f"가격: {execution_price:,.0f}원 | "
            f"금액: {amount:,.0f}원"
        )

        return result
