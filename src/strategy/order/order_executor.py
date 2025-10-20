"""주문 실행을 담당하는 모듈"""

import logging
from typing import Protocol

from src.common.google_sheet.client import GoogleSheetClient
from src.common.slack.client import SlackClient
from src.strategy.order.execution_result import ExecutionResult
from src.upbit.model.order import OrderResult
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        upbit_api: UpbitAPI,
        google_sheet_client: GoogleSheetClient | None = None,
        slack_client: SlackClient | None = None,
    ) -> None:
        """
        OrderExecutor 초기화

        Args:
            upbit_api: UpbitAPI 인스턴스
            google_sheet_client: GoogleSheetClient 인스턴스 (optional)
            slack_client: SlackClient 인스턴스 (optional)
        """
        self._upbit_api = upbit_api
        self._google_sheet_client = google_sheet_client
        self._slack_client = slack_client

    def buy(self, ticker: str, amount: float, strategy_name: str = "Unknown") -> ExecutionResult:
        """
        시장가 매수 주문 실행

        Args:
            ticker: 마켓 ID (예: "KRW-BTC")
            amount: 매수 금액 (원화)
            strategy_name: 전략 이름 (기본값: "Unknown")

        Returns:
            ExecutionResult: 체결 결과
        """
        order_result = self._upbit_api.buy_market_order_and_wait(ticker, amount)

        result = ExecutionResult.buy(strategy_name=strategy_name, order_result=order_result)

        self._handle_result(result)

        return result

    def sell(self, ticker: str, volume: float, strategy_name: str = "Unknown") -> ExecutionResult:
        """
        시장가 매도 주문 실행

        Args:
            ticker: 마켓 ID (예: "KRW-BTC")
            volume: 매도 수량
            strategy_name: 전략 이름 (기본값: "Unknown")

        Returns:
            ExecutionResult: 체결 결과
        """
        order_result: OrderResult = self._upbit_api.sell_market_order_and_wait(ticker, volume)

        result = ExecutionResult.sell(strategy_name=strategy_name, order_result=order_result)

        self._handle_result(result)

        return result

    def _handle_result(self, result: ExecutionResult) -> None:
        # TODO: 비동기?
        if self._slack_client:
            self._slack_client.send_order_notification(result)

        if self._google_sheet_client:
            self._google_sheet_client.append_order_result(result)
