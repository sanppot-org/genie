"""DI Container for application components."""

import logging

from dependency_injector import containers, providers

from src.allocation_manager import AllocatedBalanceProvider
from src.bithumb.bithumb_api import BithumbApi
from src.collector.price_data_collector import GoogleSheetDataCollector
from src.common.clock import SystemClock
from src.common.google_sheet.client import GoogleSheetClient
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.config import BithumbConfig, GoogleSheetConfig, HantuConfig, HealthcheckConfig, SlackConfig, UpbitConfig
from src.constants import KST
from src.hantu import HantuDomesticAPI
from src.report.reporter import Reporter
from src.scheduled_tasks import ScheduledTasksContext
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.strategy_context import StrategyContext
from src.strategy.volatility_strategy import VolatilityStrategy
from src.upbit.upbit_api import UpbitAPI


class ApplicationContainer(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.scheduled_tasks",
        ],
    )

    # Configuration
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

    # Google Sheet Clients
    data_google_sheet_client = providers.Singleton(GoogleSheetClient, google_sheet_config, sheet_name="auto_data")
    trades_google_sheet_client = providers.Singleton(GoogleSheetClient, google_sheet_config, sheet_name="Trades")

    # Business Components
    clock = providers.Singleton(SystemClock, KST)
    cache_manager = providers.Singleton(CacheManager)
    allocation_manager = providers.Singleton(AllocatedBalanceProvider, slack_client)
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

    # Strategy Factories
    volatility_strategy_factory = providers.Factory(
        VolatilityStrategy,
        order_executor=order_executor,
        clock=clock,
        data_collector=data_collector,
        cache_manager=cache_manager,
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
