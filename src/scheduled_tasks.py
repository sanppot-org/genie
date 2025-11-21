"""스케줄러 작업 함수들

스케줄러에서 실행되는 모든 작업 함수들을 관리합니다.
"""

from collections.abc import Callable
import logging
from time import sleep

from dependency_injector.wiring import Provide, inject

from src.allocation_manager import AllocatedBalanceProvider
from src.bithumb.bithumb_api import BithumbApi
from src.collector.price_data_collector import GoogleSheetDataCollector
from src.common.clock import Clock
from src.common.google_sheet.cell_update import CellUpdate
from src.common.google_sheet.client import GoogleSheetClient
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.constants import RESERVED_BALANCE
from src.container import ApplicationContainer
from src.report.reporter import Reporter
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.volatility_strategy import VolatilityStrategy
from src.upbit.upbit_api import UpbitAPI


class ScheduledTasksContext:
    """스케줄러 작업 실행에 필요한 의존성을 관리하는 컨텍스트

    Attributes:
        allocation_manager: 잔고 할당 관리자
        slack_client: Slack 클라이언트
        healthcheck_client: 헬스체크 클라이언트
        order_executor: 주문 실행기
        clock: 시스템 시계
        data_collector: 데이터 수집기
        cache_manager: 캐시 관리자
        tickers: 거래할 티커 목록
        total_balance: 전체 잔고
        logger: 로거
    """

    def __init__(
            self,
            allocation_manager: AllocatedBalanceProvider,
            slack_client: SlackClient,
            healthcheck_client: HealthcheckClient,
            order_executor: OrderExecutor,
            clock: Clock,
            data_collector: DataCollector,
            cache_manager: CacheManager,
            tickers: list[str],
            total_balance: int,
            logger: logging.Logger,
    ) -> None:
        self.allocation_manager = allocation_manager
        self.slack_client = slack_client
        self.healthcheck_client = healthcheck_client
        self.order_executor = order_executor
        self.clock = clock
        self.data_collector = data_collector
        self.cache_manager = cache_manager
        self.tickers = tickers
        self.total_balance = total_balance
        self.logger = logger


@inject
def run_strategies(
    context: ScheduledTasksContext = Provide[ApplicationContainer.tasks_context],
    create_volatility_strategy: Callable[[BaseStrategyConfig], VolatilityStrategy] = Provide[ApplicationContainer.volatility_strategy_factory],
) -> None:
    """1분마다 실행될 전략 실행 함수 - 의존성 자동 주입"""
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

                volatility_strategy = create_volatility_strategy(config=strategy_config)  # type: ignore[call-arg]

                try:
                    volatility_strategy.execute()
                except Exception as e:
                    context.logger.exception(f"에러 발생: {e}")
                    context.slack_client.send_status(
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


@inject
def check_upbit_status(
    upbit_api: UpbitAPI = Provide[ApplicationContainer.upbit_api],
    slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """Upbit 상태 체크 - 의존성 자동 주입"""
    if not upbit_api.get_available_amount():
        slack_client.send_status("전략에 할당된 금액이 없거나, upbit에 접근할 수 없습니다.")
        raise SystemError


@inject
def update_upbit_krw(
    upbit_api: UpbitAPI = Provide[ApplicationContainer.upbit_api],
    google_sheet_client: GoogleSheetClient = Provide[ApplicationContainer.data_google_sheet_client],
) -> None:
    """Upbit KRW 잔고를 Google Sheet에 기록 - 의존성 자동 주입

    Google Sheet의 (1, 2) 셀에 업데이트합니다.
    """
    amount = upbit_api.get_available_amount()
    row = 2
    google_sheet_client.batch_update(updates=[
        CellUpdate.data(row, amount),
        CellUpdate.now(row)
    ])

@inject
def update_bithumb_krw(
    bithumb_api: BithumbApi = Provide[ApplicationContainer.bithumb_api],
    google_sheet_client: GoogleSheetClient = Provide[ApplicationContainer.data_google_sheet_client],
) -> None:
    """Bithumb KRW 잔고를 Google Sheet에 기록 - 의존성 자동 주입"""
    amount = bithumb_api.get_available_amount("KRW")
    row = 6
    google_sheet_client.batch_update(updates=[
        CellUpdate.data(row, amount),
        CellUpdate.now(row)
    ])

@inject
def report(reporter: Reporter = Provide[ApplicationContainer.reporter]) -> None:
    """리포트 생성 - 의존성 자동 주입"""
    reporter.report()


@inject
def update_data(price_data_collector: GoogleSheetDataCollector = Provide[ApplicationContainer.price_data_collector]) -> None:
    """구글 시트 데이터 업데이트 - 의존성 자동 주입"""
    price_data_collector.collect_price()
