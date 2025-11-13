import logging

from src.allocation_manager import AllocatedBalanceProvider
from src.collector.price_data_collector import PriceDataCollector
from src.common.clock import SystemClock
from src.common.google_sheet.client import GoogleSheetClient
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.config import GoogleSheetConfig, HantuConfig, HealthcheckConfig, SlackConfig, UpbitConfig
from src.constants import KST
from src.hantu import HantuDomesticAPI
from src.scheduled_tasks import (
    ScheduledTasksContext,
    check_upbit_status,
    report,
    run_strategies,
    update_gold_price,
    update_upbit_krw,
)
from src.scheduler_setup import setup_scheduler
from src.logging_config import setup_logging
from src.report.reporter import Reporter
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.strategy_context import StrategyContext
from src.upbit.upbit_api import UpbitAPI

# Better Stack 로깅 설정 (가장 먼저 실행)
setup_logging()
logger = logging.getLogger(__name__)

# TODO: DB 설정
total_balance = 110_000_000
tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]

data_google_sheet_client = GoogleSheetClient(GoogleSheetConfig(), sheet_name="data")

# 공유 클라이언트 및 헬스체크
slack_client = SlackClient(SlackConfig())
healthcheck_client = HealthcheckClient(HealthcheckConfig())
allocation_manager = AllocatedBalanceProvider(slack_client)
upbit_api = UpbitAPI(UpbitConfig())

# 전략 실행에 필요한 공유 컴포넌트들 (1분마다 재사용)
clock = SystemClock(KST)
data_collector = DataCollector(clock, slack_client)
trades_google_sheet_client = GoogleSheetClient(GoogleSheetConfig(), sheet_name="Trades")
cache_manager = CacheManager()
order_executor = OrderExecutor(upbit_api, google_sheet_client=trades_google_sheet_client, slack_client=slack_client)

hantu_domestic_api = HantuDomesticAPI(HantuConfig())
reporter = Reporter(upbit_api=upbit_api, hantu_api=hantu_domestic_api, slack_cient=slack_client)
price_data_collector = PriceDataCollector(hantu_api=hantu_domestic_api, google_sheet_client=data_google_sheet_client)

# 전략 컨텍스트 생성
strategy_context = StrategyContext(
    clock=clock,
    data_collector=data_collector,
    google_sheet_client=trades_google_sheet_client,
    slack_client=slack_client,
    upbit_api=upbit_api,
    order_executor=order_executor,
    cache_manager=cache_manager,
)

# 스케줄러 작업 컨텍스트 생성
tasks_context = ScheduledTasksContext(
    allocation_manager=allocation_manager,
    upbit_api=upbit_api,
    slack_client=slack_client,
    healthcheck_client=healthcheck_client,
    reporter=reporter,
    price_data_collector=price_data_collector,
    data_google_sheet_client=data_google_sheet_client,
    strategy_context=strategy_context,
    tickers=tickers,
    total_balance=total_balance,
    logger=logger,
)

if __name__ == "__main__":
    check_upbit_status(tasks_context)

    # 스케줄러 설정
    scheduler = setup_scheduler(
        report_func=lambda: report(tasks_context),
        update_upbit_krw_func=lambda: update_upbit_krw(tasks_context),
        run_strategies_func=lambda: run_strategies(tasks_context),
        update_gold_price_func=lambda: update_gold_price(tasks_context),
    )

    # 즉시 한 번 실행
    run_strategies(tasks_context)

    try:
        # 스케줄러 시작 (블로킹)
        logger.info("암호화폐 자동 매매 스케줄러 시작 (1분마다 실행)")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
