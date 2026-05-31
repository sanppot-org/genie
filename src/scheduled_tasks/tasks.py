"""스케줄러 작업 함수들

스케줄러에서 실행되는 모든 작업 함수들을 관리합니다.
"""

from datetime import datetime, timedelta
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
from src.scheduled_tasks.scope import db_scoped, mark_rollback_only
from src.service.buyback_sync_service import BuybackSyncService
from src.service.cancellation_sync_service import CancellationSyncService
from src.service.daily_candle_sync_service import DailyCandleSyncService
from src.service.dividend_sync_service import DividendSyncService
from src.service.financial_ratio_sync_service import FinancialRatioSyncService
from src.service.fundamental_sync_service import FundamentalSyncService
from src.service.income_statement_sync_service import IncomeStatementSyncService
from src.service.ticker_sync_service import TickerSyncService
from src.service.treasury_stock_sync_service import TreasuryStockSyncService
from src.strategy.config import BaseStrategyConfig
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


@db_scoped
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


@db_scoped
@inject
def check_upbit_status(
        upbit_api: UpbitAPI = Provide[ApplicationContainer.upbit_api],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """Upbit 상태 체크 - 의존성 자동 주입"""
    if not upbit_api.get_available_amount():
        slack_client.send_status("전략에 할당된 금액이 없거나, upbit에 접근할 수 없습니다.")
        raise SystemError


@db_scoped
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


@db_scoped
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


@db_scoped
@inject
def report(reporter: Reporter = Provide[ApplicationContainer.reporter]) -> None:
    """리포트 생성 - 의존성 자동 주입"""
    reporter.report()


@db_scoped
@inject
def update_data(
        price_data_collector: GoogleSheetDataCollector = Provide[ApplicationContainer.price_data_collector]) -> None:
    """구글 시트 데이터 업데이트 - 의존성 자동 주입"""
    price_data_collector.collect_price()


@db_scoped
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
        mark_rollback_only()
        logger.exception("한국 주식 종목 동기화 실패")
        slack_client.send_status(f"한국 주식 종목 동기화 실패: {e}")


@db_scoped
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
        mark_rollback_only()
        logger.exception("펀더멘털 동기화 실패")
        slack_client.send_status(f"펀더멘털 동기화 실패 ({target_date}): {e}")


@db_scoped
@inject
def sync_kr_stock_dividends(
        service: DividendSyncService = Provide[ApplicationContainer.dividend_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """KR 주식 배당 이력 동기화 (일 1회).

    최근 30일 ~ 향후 60일 범위로 호출 → 배당락일이 사전 공지된 분도 미리 수집.
    매일 멱등 UPSERT라 중복 호출에도 데이터 무결성 유지.
    """
    today = datetime.now(KST).date()
    from_date = today - timedelta(days=30)
    to_date = today + timedelta(days=60)
    try:
        result = service.sync(from_date, to_date)
        logger.info(
            "배당 동기화 완료 from=%s to=%s received=%d upserted=%d skipped_unmapped=%d skipped_invalid=%d",
            from_date, to_date, result.received, result.upserted,
            result.skipped_unmapped, result.skipped_invalid,
        )
    except Exception as e:
        mark_rollback_only()
        logger.exception("배당 동기화 실패")
        slack_client.send_status(f"배당 동기화 실패 ({from_date}~{to_date}): {e}")


@db_scoped
@inject
def sync_kr_stock_buybacks(
        service: BuybackSyncService = Provide[ApplicationContainer.buyback_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """KR 주식 자기주식 취득·처분 공시 동기화 (주 1회, 매주 월요일 18:30 KST).

    DART 공시는 수시 발생 → 분기 폴링은 너무 느림. 주 1회 충분.
    최근 90일을 안전 buffer로 매번 호출 (수정·정정 공시 반영).
    """
    today = datetime.now(KST).date()
    from_date = today - timedelta(days=90)
    try:
        result = service.sync(from_date, today)
        logger.info(
            "자사주 공시 동기화 완료 from=%s to=%s tickers=%d received=%d upserted=%d skipped_failure=%d",
            from_date, today, result.tickers, result.received,
            result.upserted, result.skipped_failure,
        )
    except Exception as e:
        mark_rollback_only()
        logger.exception("자사주 공시 동기화 실패")
        slack_client.send_status(f"자사주 공시 동기화 실패 ({from_date}~{today}): {e}")


@db_scoped
@inject
def sync_kr_stock_cancellations(
        service: CancellationSyncService = Provide[ApplicationContainer.cancellation_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """KR 주식 주식소각결정 공시(자사주 소각) 동기화 (주 1회, 매주 월요일 19:30 KST).

    DART 공시는 수시 발생 → 분기 폴링은 너무 느림. 주 1회 충분.
    최근 90일을 안전 buffer로 매번 호출 (수정·정정 공시 반영). 멱등 UPSERT라 중복 호출 안전.
    초기 전종목 백필은 scripts/backfill_cancellations.py 사용.
    """
    today = datetime.now(KST).date()
    from_date = today - timedelta(days=90)
    try:
        result = service.sync(from_date, today)
        logger.info(
            "주식소각결정 동기화 완료 from=%s to=%s tickers=%d api_fail=%d rows_upserted=%d chunks_fail=%d",
            from_date, today, result.ticker_count, result.api_calls_failed,
            result.rows_upserted, result.chunks_failed,
        )
    except Exception as e:
        mark_rollback_only()
        logger.exception("주식소각결정 동기화 실패")
        slack_client.send_status(f"주식소각결정 동기화 실패 ({from_date}~{today}): {e}")


@db_scoped
@inject
def sync_kr_stock_income_statements(
        service: IncomeStatementSyncService = Provide[ApplicationContainer.income_statement_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """KR 주식 손익계산서 동기화 (주 1회, 매주 월요일 19:00 KST).

    재무는 분기 갱신이라 주 1회로 충분. 증분 가드(skip_current)로 이미 최신 분기를
    커버한 종목은 호출 생략. 청크 커밋이라 부분 진행도 보존되며 멱등 재실행 안전.
    초기 전종목 백필은 scripts/backfill_income_statements.py 사용.
    """
    try:
        result = service.sync(skip_current=True)
        logger.info(
            "손익계산서 동기화 완료 tickers=%d skipped_current=%d api_fail=%d rows_upserted=%d chunks_fail=%d",
            result.ticker_count, result.skipped_current, result.api_calls_failed,
            result.rows_upserted, result.chunks_failed,
        )
    except Exception as e:
        mark_rollback_only()
        logger.exception("손익계산서 동기화 실패")
        slack_client.send_status(f"손익계산서 동기화 실패: {e}")


@db_scoped
@inject
def sync_kr_stock_financial_ratios(
        service: FinancialRatioSyncService = Provide[ApplicationContainer.financial_ratio_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """KR 주식 재무비율(ROE·성장률·부채비율 등) 동기화 (주 1회, 매주 월요일 19:45 KST).

    재무는 분기/연간 갱신이라 주 1회로 충분. 증분 가드(skip_current)로 이미 최신 사업보고서를
    커버한 종목은 호출 생략. 청크 커밋이라 부분 진행도 보존되며 멱등 재실행 안전.
    초기 전종목 백필은 scripts/backfill_financial_ratios.py 사용.
    """
    try:
        result = service.sync(skip_current=True)
        logger.info(
            "재무비율 동기화 완료 tickers=%d skipped_current=%d api_fail=%d rows_upserted=%d chunks_fail=%d",
            result.ticker_count, result.skipped_current, result.api_calls_failed,
            result.rows_upserted, result.chunks_failed,
        )
    except Exception as e:
        mark_rollback_only()
        logger.exception("재무비율 동기화 실패")
        slack_client.send_status(f"재무비율 동기화 실패: {e}")


@db_scoped
@inject
def sync_kr_stock_treasury_stocks(
        service: TreasuryStockSyncService = Provide[ApplicationContainer.treasury_stock_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """KR 주식 자사주 보유 비율 동기화 (월 2회, 매월 1일/16일 18:00 KST).

    DART 정기보고서(사업/반기/Q1/Q3) 기반이라 갱신은 분기 1회뿐.
    월 2회 폴링으로 보고서 제출 지연 시 누락 방지.
    """
    target_date = datetime.now(KST).date()
    try:
        result = service.sync(target_date)
        logger.info(
            "자사주 동기화 완료 bsns_year=%d reprt_code=%s tickers=%d upserted=%d skipped_no_data=%d skipped_failure=%d",
            result.bsns_year, result.reprt_code, result.tickers,
            result.upserted, result.skipped_no_data, result.skipped_failure,
        )
    except Exception as e:
        mark_rollback_only()
        logger.exception("자사주 동기화 실패")
        slack_client.send_status(f"자사주 동기화 실패: {e}")


@db_scoped
@inject
def sync_kr_stock_daily_candles(
        service: DailyCandleSyncService = Provide[ApplicationContainer.daily_candle_sync_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """일자별 KR 주식 일봉 동기화 (장 마감 후, 평일).

    휴장일은 pykrx 빈 응답/거래량 0 → `KrxClosedDayError`/`EmptyPykrxResponseError`로
    도착 → info 로그만 남기고 종료. 그 외 예외만 Slack 알림.
    """
    target_date = datetime.now(KST).date()
    try:
        result = service.sync(target_date)
        logger.info(
            "일봉 동기화 완료 date=%s received=%d upserted=%d skipped_unmapped=%d skipped_no_trade=%d",
            target_date, result.received, result.upserted,
            result.skipped_unmapped, result.skipped_no_trade,
        )
    except (KrxClosedDayError, EmptyPykrxResponseError) as e:
        logger.info("일봉 동기화 skip date=%s reason=%s", target_date, e)
    except Exception as e:
        mark_rollback_only()
        logger.exception("일봉 동기화 실패")
        slack_client.send_status(f"일봉 동기화 실패 ({target_date}): {e}")
