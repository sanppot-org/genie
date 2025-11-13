"""스케줄러 작업 함수들

스케줄러에서 실행되는 모든 작업 함수들을 관리합니다.
"""

import logging
from time import sleep

from src.allocation_manager import AllocatedBalanceProvider
from src.collector.price_data_collector import GoogleSheetDataCollector
from src.common.google_sheet.cell_update import CellUpdate
from src.common.google_sheet.client import GoogleSheetClient
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.constants import RESERVED_BALANCE
from src.report.reporter import Reporter
from src.strategy.config import BaseStrategyConfig
from src.strategy.strategy_context import StrategyContext
from src.strategy.volatility_strategy import VolatilityStrategy
from src.upbit.upbit_api import UpbitAPI


class ScheduledTasksContext:
    """스케줄러 작업 실행에 필요한 의존성을 관리하는 컨텍스트

    Attributes:
        allocation_manager: 잔고 할당 관리자
        upbit_api: Upbit API 클라이언트
        slack_client: Slack 클라이언트
        healthcheck_client: 헬스체크 클라이언트
        reporter: 리포트 생성기
        price_data_collector: 가격 데이터 수집기
        data_google_sheet_client: 데이터 저장용 Google Sheet 클라이언트
        strategy_context: 전략 실행 컨텍스트
        tickers: 거래할 티커 목록
        total_balance: 전체 잔고
        logger: 로거
    """

    def __init__(
            self,
            allocation_manager: AllocatedBalanceProvider,
            upbit_api: UpbitAPI,
            slack_client: SlackClient,
            healthcheck_client: HealthcheckClient,
            reporter: Reporter,
            price_data_collector: GoogleSheetDataCollector,
            data_google_sheet_client: GoogleSheetClient,
            strategy_context: StrategyContext,
            tickers: list[str],
            total_balance: int,
            logger: logging.Logger,
    ) -> None:
        self.allocation_manager = allocation_manager
        self.upbit_api = upbit_api
        self.slack_client = slack_client
        self.healthcheck_client = healthcheck_client
        self.reporter = reporter
        self.price_data_collector = price_data_collector
        self.data_google_sheet_client = data_google_sheet_client
        self.strategy_context = strategy_context
        self.tickers = tickers
        self.total_balance = total_balance
        self.logger = logger


def run_strategies(context: ScheduledTasksContext) -> None:
    """1분마다 실행될 전략 실행 함수"""
    try:
        balance = context.allocation_manager.get_allocated_amount()
        allocated_balance = (balance - RESERVED_BALANCE) / len(context.tickers)

        for ticker in context.tickers:
            try:
                strategy_config = BaseStrategyConfig(
                    ticker=ticker,
                    total_balance=context.total_balance,
                    allocated_balance=allocated_balance,
                )

                volatility_strategy = VolatilityStrategy(
                    context.strategy_context.order_executor,
                    strategy_config,
                    context.strategy_context.clock,
                    context.strategy_context.data_collector,
                    context.strategy_context.cache_manager,
                )

                try:
                    volatility_strategy.execute()
                except Exception as e:
                    context.logger.exception(f"에러 발생: {e}")
                    context.strategy_context.slack_client.send_status(
                        f"{ticker} 변동성 돌파 전략 에러 발생. log: {e}"
                    )

                sleep(0.5)
            except Exception as e:
                context.logger.error(f"{ticker} 전략 실행 실패: {e}", exc_info=True)
                context.slack_client.send_status(f"{ticker} 전략 실행 실패: {e}")

        # 헬스체크 ping 전송 (성공 시)
        context.healthcheck_client.ping()
    except Exception as e:
        context.logger.error(f"전략 실행 중 예외 발생: {e}", exc_info=True)
        context.slack_client.send_status(f"전략 실행 중 예외 발생: {e}")


def check_upbit_status(context: ScheduledTasksContext) -> None:
    """Upbit 상태 체크"""
    if not context.upbit_api.get_available_amount():
        context.slack_client.send_status("전략에 할당된 금액이 없거나, upbit에 접근할 수 없습니다.")
        raise SystemError


def update_upbit_krw(context: ScheduledTasksContext) -> None:
    """Upbit KRW 잔고를 Google Sheet에 기록

    Google Sheet의 (1, 2) 셀에 업데이트합니다.
    """
    amount = context.upbit_api.get_available_amount()
    context.data_google_sheet_client.batch_update(updates=[
        CellUpdate.data(2, amount),
        CellUpdate.now(2)
    ])


def report(context: ScheduledTasksContext) -> None:
    """리포트 생성"""
    context.reporter.report()


def update_data(context: ScheduledTasksContext) -> None:
    """구글 시트 데이터 업데이트"""
    context.price_data_collector.collect_price()
