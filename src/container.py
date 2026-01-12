"""DI Container for application components."""

import logging

from dependency_injector import containers, providers

from src.adapters.adapter_factory import CandleAdapterFactory
from src.allocation_manager import AllocatedBalanceProvider
from src.bithumb.bithumb_api import BithumbApi
from src.collector.price_data_collector import GoogleSheetDataCollector
from src.common.clock import SystemClock
from src.common.google_sheet.client import GoogleSheetClient
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.config import BithumbConfig, DatabaseConfig, GoogleSheetConfig, HantuConfig, HealthcheckConfig, SlackConfig, UpbitConfig
from src.constants import KST
from src.database.database import Database
from src.database.repositories import CandleDailyRepository, CandleHour1Repository, CandleMinute1Repository
from src.database.ticker_repository import TickerRepository
from src.hantu import HantuDomesticAPI
from src.report.reporter import Reporter
from src.scheduled_tasks.context import ScheduledTasksContext
from src.service.candle_service import CandleService
from src.service.ticker_service import TickerService
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.strategy_context import StrategyContext
from src.upbit.upbit_api import UpbitAPI


class ApplicationContainer(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.scheduled_tasks.tasks",  # tasks.py를 가리킴
            "src.api.lifespan",  # lifespan.py 추가
            "src.api.routes.strategy",  # strategy 라우터 추가
            "src.api.routes.ticker",  # ticker 라우터 추가
            "src.api.routes.candle",  # candle 라우터 추가
            "src.strategy.factory",  # factory.py 추가
        ],
    )

    # Configuration
    database_config = providers.Singleton(DatabaseConfig)
    google_sheet_config = providers.Singleton(GoogleSheetConfig)
    slack_config = providers.Singleton(SlackConfig)
    upbit_config = providers.Singleton(UpbitConfig)
    bithumb_config = providers.Singleton(BithumbConfig)
    hantu_config = providers.Singleton(HantuConfig)
    healthcheck_config = providers.Singleton(HealthcheckConfig)

    # Clients
    slack_client = providers.Singleton(SlackClient, slack_config)
    healthcheck_client = providers.Singleton(HealthcheckClient, healthcheck_config)
    upbit_api = providers.Singleton(UpbitAPI, upbit_config)
    bithumb_api = providers.Singleton(BithumbApi, bithumb_config)
    hantu_domestic_api = providers.Singleton(HantuDomesticAPI, hantu_config)

    # Database
    database = providers.Singleton(Database, database_config)
    candle_minute1_repository = providers.Factory(CandleMinute1Repository, session=database.provided.get_session.call())
    candle_hour1_repository = providers.Factory(CandleHour1Repository, session=database.provided.get_session.call())
    candle_daily_repository = providers.Factory(CandleDailyRepository, session=database.provided.get_session.call())
    ticker_repository = providers.Factory(TickerRepository, session=database.provided.get_session.call())

    # Google Sheet Clients
    data_google_sheet_client = providers.Singleton(GoogleSheetClient, google_sheet_config, sheet_name="auto_data")
    trades_google_sheet_client = providers.Singleton(GoogleSheetClient, google_sheet_config, sheet_name="Trades")

    # Business Components
    clock = providers.Singleton(SystemClock, KST)
    cache_manager = providers.Singleton(CacheManager)
    allocation_manager = providers.Singleton(AllocatedBalanceProvider, slack_client, upbit_api)
    data_collector = providers.Singleton(DataCollector, clock, slack_client)
    order_executor = providers.Singleton(
        OrderExecutor,
        upbit_api,
        google_sheet_client=trades_google_sheet_client,
        slack_client=slack_client,
    )
    reporter = providers.Singleton(
        Reporter,
        upbit_api=upbit_api,
        hantu_api=hantu_domestic_api,
        slack_cient=slack_client,
    )
    price_data_collector = providers.Singleton(
        GoogleSheetDataCollector,
        hantu_api=hantu_domestic_api,
        google_sheet_client=data_google_sheet_client,
    )

    # Strategy Context
    strategy_context = providers.Singleton(
        StrategyContext,
        clock=clock,
        data_collector=data_collector,
        google_sheet_client=trades_google_sheet_client,
        slack_client=slack_client,
        upbit_api=upbit_api,
        order_executor=order_executor,
        cache_manager=cache_manager,
    )

    # Scheduled Tasks Context
    tasks_context = providers.Singleton(
        ScheduledTasksContext,
        allocation_manager=allocation_manager,
        slack_client=slack_client,
        healthcheck_client=healthcheck_client,
        order_executor=order_executor,
        clock=clock,
        data_collector=data_collector,
        cache_manager=cache_manager,
        tickers=["KRW-BTC", "KRW-ETH", "KRW-XRP"],
        total_balance=115_000_000,
        logger=providers.Object(logging.getLogger(__name__)),
    )

    # Adapters
    candle_adapter_factory = providers.Singleton(CandleAdapterFactory)

    # Services
    candle_service = providers.Factory(
        CandleService,
        minute1_repository=candle_minute1_repository,
        daily_repository=candle_daily_repository,
        adapter_factory=candle_adapter_factory,
    )
    ticker_service = providers.Factory(
        TickerService,
        repository=ticker_repository,
    )
