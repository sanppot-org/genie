import logging
from time import sleep

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.allocation_manager import AllocatedBalanceProvider
from src.common.clock import SystemClock
from src.common.google_sheet.client import GoogleSheetClient
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.config import GoogleSheetConfig, HealthcheckConfig, SlackConfig, UpbitConfig
from src.constants import KST, RESERVED_BALANCE
from src.logging_config import setup_logging
from src.strategy import o_dol_strategy
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.strategy_context import StrategyContext
from src.upbit.upbit_api import UpbitAPI

# Better Stack 로깅 설정 (가장 먼저 실행)
setup_logging()
logger = logging.getLogger(__name__)

# TODO: DB 설정
total_balance = 100_000_000
tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]

# 공유 클라이언트 및 헬스체크
slack_client = SlackClient(SlackConfig())
healthcheck_client = HealthcheckClient(HealthcheckConfig())
allocation_manager = AllocatedBalanceProvider(slack_client)
upbit_api = UpbitAPI(UpbitConfig())

# 전략 실행에 필요한 공유 컴포넌트들 (1분마다 재사용)
clock = SystemClock(KST)
data_collector = DataCollector(clock, slack_client)
google_sheet_client = GoogleSheetClient(GoogleSheetConfig())
cache_manager = CacheManager()
order_executor = OrderExecutor(upbit_api, google_sheet_client=google_sheet_client, slack_client=slack_client)

# 전략 컨텍스트 생성
strategy_context = StrategyContext(
    clock=clock,
    data_collector=data_collector,
    google_sheet_client=google_sheet_client,
    slack_client=slack_client,
    upbit_api=upbit_api,
    order_executor=order_executor,
    cache_manager=cache_manager,
)


def run_strategies() -> None:
    """1분마다 실행될 전략 실행 함수"""
    try:
        balance = allocation_manager.get_allocated_amount()
        allocated_balance = (balance - RESERVED_BALANCE) / len(tickers)

        for ticker in tickers:
            try:
                o_dol_strategy.run(
                    ticker=ticker, total_balance=total_balance, allocated_balance=allocated_balance, context=strategy_context
                )
                sleep(0.5)
            except Exception as e:
                logger.error(f"{ticker} 전략 실행 실패: {e}", exc_info=True)
                slack_client.send_status(f"{ticker} 전략 실행 실패: {e}")

        # 헬스체크 ping 전송 (성공 시)
        healthcheck_client.ping()
    except Exception as e:
        logger.error(f"전략 실행 중 예외 발생: {e}", exc_info=True)
        slack_client.send_status(f"전략 실행 중 예외 발생: {e}")


def check_upbit_status() -> None:
    if not upbit_api.get_available_amount():
        slack_client.send_status("전략에 할당된 금액이 없거나, upbit에 접근할 수 없습니다.")
        raise SystemError


if __name__ == "__main__":
    check_upbit_status()

    # 스케줄러 초기화
    scheduler = BlockingScheduler()

    # 1분마다 실행하도록 스케줄 등록
    scheduler.add_job(
        run_strategies,
        trigger=IntervalTrigger(minutes=1),
        id="crypto_trading",
        name="암호화폐 자동 매매",
        replace_existing=True,
    )

    # 즉시 한 번 실행
    run_strategies()

    try:
        # 스케줄러 시작 (블로킹)
        logger.info("암호화폐 자동 매매 스케줄러 시작 (1분마다 실행)")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
