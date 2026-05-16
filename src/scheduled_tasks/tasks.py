"""스케줄러 작업 함수들

스케줄러에서 실행되는 모든 작업 함수들을 관리합니다.
"""

from datetime import datetime
import logging
from time import sleep

from dependency_injector.wiring import Provide, inject

from src.bithumb.bithumb_api import BithumbApi
from src.collector.price_data_collector import GoogleSheetDataCollector
from src.common.google_sheet.cell_update import CellUpdate
from src.common.google_sheet.client import GoogleSheetClient
from src.common.slack.client import SlackClient
from src.constants import KST, MIN_ALLOCATED_BALANCE, RESERVED_BALANCE
from src.container import ApplicationContainer
from src.providers.pykrx_fundamental_client import KrxClosedDayError
from src.providers.pykrx_ticker_client import EmptyPykrxResponseError
from src.report.reporter import Reporter
from src.scheduled_tasks.context import ScheduledTasksContext
from src.service.fundamental_sync_service import FundamentalSyncService
from src.service.ticker_sync_service import TickerSyncService
from src.strategy.config import BaseStrategyConfig
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


@inject
def run_strategies(
        context: ScheduledTasksContext = Provide[ApplicationContainer.tasks_context],
) -> None:
    """1분마다 실행될 전략 실행 함수 - 의존성 자동 주입"""
    try:
        balance = context.allocation_manager.get_allocated_amount()
        allocated_balance = (balance - RESERVED_BALANCE) / len(context.tickers)

        if allocated_balance < MIN_ALLOCATED_BALANCE:
            context.logger.info(f"잔고 부족으로 전략 실행 스킵. balance: {balance}, allocated: {allocated_balance}")
            context.healthcheck_client.ping()
            return

        for ticker in context.tickers:
            try:
                strategy_config = BaseStrategyConfig(
                    ticker=ticker,
                    total_balance=context.total_balance,
                    allocated_balance=allocated_balance,
                )

                volatility_strategy = context.create_volatility_strategy(config=strategy_config)

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
def update_data(
        price_data_collector: GoogleSheetDataCollector = Provide[ApplicationContainer.price_data_collector]) -> None:
    """구글 시트 데이터 업데이트 - 의존성 자동 주입"""
    price_data_collector.collect_price()


@inject
def sync_kr_stock_tickers(
        service: TickerSyncService = Provide[ApplicationContainer.ticker_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """한국 주식/ETF 종목 정보를 pykrx에서 가져와 DB와 동기화.

    pykrx 빈 응답은 client가 재시도 후 예외를 raise하므로, 여기서는 예외 발생 시
    Slack 알림만 처리한다.
    """
    try:
        result = service.sync_pykrx()
        logger.info(
            "한국 주식 종목 동기화 완료: inserted=%d, deactivated=%d, renamed=%d, reactivated=%d, unchanged=%d",
            result.inserted, result.deactivated, result.renamed, result.reactivated, result.unchanged,
        )
    except Exception as e:
        logger.exception("한국 주식 종목 동기화 실패")
        slack_client.send_status(f"한국 주식 종목 동기화 실패: {e}")


@inject
def sync_kr_stock_fundamentals(
        service: FundamentalSyncService = Provide[ApplicationContainer.fundamental_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """일자별 KR 주식 펀더멘털 동기화 (장 마감 후, 평일).

    휴장일은 pykrx가 빈 응답 → `EmptyPykrxResponseError`로 도착 → info 로그만 남기고 종료.
    그 외 예외만 Slack 알림.
    """
    target_date = datetime.now(KST).date()
    try:
        result = service.sync(target_date)
        logger.info(
            "펀더멘털 동기화 완료 date=%s received=%d upserted=%d skipped_unmapped=%d",
            target_date, result.received, result.upserted, result.skipped_unmapped,
        )
    except (KrxClosedDayError, EmptyPykrxResponseError) as e:
        logger.info("펀더멘털 동기화 skip date=%s reason=%s", target_date, e)
    except Exception as e:
        logger.exception("펀더멘털 동기화 실패")
        slack_client.send_status(f"펀더멘털 동기화 실패 ({target_date}): {e}")
