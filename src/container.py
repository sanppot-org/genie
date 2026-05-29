"""DI Container for application components."""

import logging

from dependency_injector import containers, providers
from sqlalchemy.orm import Session

from src.adapters.adapter_factory import CandleAdapterFactory
from src.allocation_manager import AllocatedBalanceProvider
from src.bithumb.bithumb_api import BithumbApi
from src.collector.price_data_collector import GoogleSheetDataCollector
from src.common.clock import SystemClock
from src.common.data_adapter import DataSource
from src.common.google_sheet.client import GoogleSheetClient
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.config import BithumbConfig, DatabaseConfig, GoogleSheetConfig, HantuConfig, HealthcheckConfig, OpenDartConfig, SlackConfig, UpbitConfig
from src.constants import KST
from src.database.database import Database
from src.database.repositories import CandleDailyRepository, CandleHour1Repository, CandleMinute1Repository
from src.database.request_scope import current_request_token
from src.database.stock_buyback_event_repository import StockBuybackEventRepository
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.database.stock_treasury_stock_repository import StockTreasuryStockRepository
from src.database.ticker_repository import TickerRepository
from src.hantu import HantuDomesticAPI, HantuOverseasAPI
from src.providers import HantuOverseasCandleClient
from src.providers.binance_candle_client import BinanceCandleClient
from src.providers.dart_company_client import DartCompanyClient
from src.providers.hantu_candle_client import HantuDomesticCandleClient
from src.providers.kis_company_client import KisCompanyClient
from src.providers.kis_income_statement_client import KisIncomeStatementClient
from src.providers.pykrx_daily_candle_client import PykrxDailyCandleClient
from src.providers.pykrx_fundamental_client import PykrxFundamentalClient
from src.providers.pykrx_ticker_client import PykrxTickerClient
from src.providers.upbit_candle_client import UpbitCandleClient
from src.report.reporter import Reporter
from src.scheduled_tasks.context import ScheduledTasksContext
from src.service.buyback_service import BuybackService
from src.service.buyback_sync_service import BuybackSyncService
from src.service.candle_query_service import CandleQueryService
from src.service.candle_service import CandleService
from src.service.daily_candle_sync_service import DailyCandleSyncService
from src.service.dividend_service import DividendService
from src.service.dividend_sync_service import DividendSyncService
from src.service.fundamental_service import FundamentalService
from src.service.fundamental_sync_service import FundamentalSyncService
from src.service.income_statement_service import IncomeStatementService
from src.service.income_statement_sync_service import IncomeStatementSyncService
from src.service.screening_service import ScreeningService
from src.service.stock_daily_candle_service import StockDailyCandleService
from src.service.ticker_service import TickerService
from src.service.ticker_sync_service import TickerSyncService
from src.service.treasury_stock_sync_service import TreasuryStockSyncService
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.strategy_context import StrategyContext
from src.upbit.upbit_api import UpbitAPI
from util.binance.binance_api import BinanceAPI


def _resolve_session(db: Database) -> Session:
    """리포지토리용 세션 해석.

    스코프 토큰이 활성(HTTP 미들웨어 또는 `@db_scoped` 스케줄러 task)이면
    scoped_session 레지스트리의 세션을 공유(같은 단위의 모든 리포가 동일
    Session, 진입점이 종료 시 `.remove()`로 정리 → 누수 없음). 토큰 미설정
    경로(테스트 직접 호출 등)는 레거시 `get_session()` 폴백.
    """
    if current_request_token() is not None:
        return db.RequestSession()
    return db.get_session()


class ApplicationContainer(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.scheduled_tasks.tasks",  # tasks.py를 가리킴
            "src.api.lifespan",  # lifespan.py 추가
            "src.api.routes.strategy",  # strategy 라우터 추가
            "src.api.routes.ticker",  # ticker 라우터 추가
            "src.api.routes.candle",  # candle 라우터 추가
            "src.api.routes.fundamental",  # fundamental 라우터 추가
            "src.api.routes.dividend",  # dividend 라우터 추가
            "src.api.routes.income_statement",  # 손익계산서 라우터 추가
            "src.api.routes.screening",  # screening 라우터 추가
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
    opendart_config = providers.Singleton(OpenDartConfig)

    # Clients
    slack_client = providers.Singleton(SlackClient, slack_config)
    healthcheck_client = providers.Singleton(HealthcheckClient, healthcheck_config)
    upbit_api = providers.Singleton(UpbitAPI, upbit_config)
    bithumb_api = providers.Singleton(BithumbApi, bithumb_config)
    hantu_domestic_api = providers.Singleton(HantuDomesticAPI, hantu_config)
    hantu_overseas_api = providers.Singleton(HantuOverseasAPI, hantu_config)

    # Database
    database = providers.Singleton(Database, database_config)
    # 요청 스코프 세션 공유(없으면 레거시 폴백) — DB 커넥션 누수 차단(Phase 1).
    _session = providers.Callable(_resolve_session, database)
    candle_minute1_repository = providers.Factory(CandleMinute1Repository, session=_session)
    candle_hour1_repository = providers.Factory(CandleHour1Repository, session=_session)
    candle_daily_repository = providers.Factory(CandleDailyRepository, session=_session)
    ticker_repository = providers.Factory(TickerRepository, session=_session)
    stock_fundamental_repository = providers.Factory(StockFundamentalRepository, session=_session)
    stock_daily_candle_repository = providers.Factory(StockDailyCandleRepository, session=_session)
    stock_dividend_repository = providers.Factory(StockDividendRepository, session=_session)
    stock_treasury_stock_repository = providers.Factory(StockTreasuryStockRepository, session=_session)
    stock_buyback_event_repository = providers.Factory(StockBuybackEventRepository, session=_session)
    stock_income_statement_repository = providers.Factory(StockIncomeStatementRepository, session=_session)

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

    # Candle Clients
    binance_api = providers.Singleton(BinanceAPI)
    upbit_candle_client = providers.Singleton(UpbitCandleClient, upbit_api)
    binance_candle_client = providers.Singleton(BinanceCandleClient, binance_api)
    hantu_overseas_candle_client = providers.Singleton(HantuOverseasCandleClient, hantu_overseas_api)
    hantu_domestic_candle_client = providers.Singleton(HantuDomesticCandleClient, hantu_domestic_api)

    # Services
    candle_query_service = providers.Factory(
        CandleQueryService,
        clients=providers.Dict({
            DataSource.UPBIT: upbit_candle_client,
            DataSource.BINANCE: binance_candle_client,
            DataSource.HANTU_O: hantu_overseas_candle_client,
            DataSource.HANTU_D: hantu_domestic_candle_client,
        }),
    )
    candle_service = providers.Factory(
        CandleService,
        minute1_repository=candle_minute1_repository,
        daily_repository=candle_daily_repository,
        adapter_factory=candle_adapter_factory,
        query_service=candle_query_service,
    )
    ticker_service = providers.Factory(
        TickerService,
        repository=ticker_repository,
    )
    pykrx_ticker_client = providers.Singleton(PykrxTickerClient)
    dart_company_client = providers.Singleton(DartCompanyClient, opendart_config)
    kis_company_client = providers.Singleton(KisCompanyClient, hantu_domestic_api)
    ticker_sync_service = providers.Factory(
        TickerSyncService,
        client=pykrx_ticker_client,
        repository=ticker_repository,
        kis_client=kis_company_client,
    )
    pykrx_fundamental_client = providers.Singleton(PykrxFundamentalClient)
    fundamental_sync_service = providers.Factory(
        FundamentalSyncService,
        client=pykrx_fundamental_client,
        ticker_repository=ticker_repository,
        fundamental_repository=stock_fundamental_repository,
    )
    fundamental_service = providers.Factory(
        FundamentalService,
        ticker_repository=ticker_repository,
        fundamental_repository=stock_fundamental_repository,
    )
    stock_daily_candle_service = providers.Factory(
        StockDailyCandleService,
        ticker_repository=ticker_repository,
        daily_candle_repository=stock_daily_candle_repository,
    )
    pykrx_daily_candle_client = providers.Singleton(PykrxDailyCandleClient)
    daily_candle_sync_service = providers.Factory(
        DailyCandleSyncService,
        client=pykrx_daily_candle_client,
        ticker_repository=ticker_repository,
        daily_candle_repository=stock_daily_candle_repository,
    )
    dividend_sync_service = providers.Factory(
        DividendSyncService,
        client=hantu_domestic_api,
        ticker_repository=ticker_repository,
        dividend_repository=stock_dividend_repository,
    )
    dividend_service = providers.Factory(
        DividendService,
        dividend_repository=stock_dividend_repository,
        ticker_repository=ticker_repository,
    )
    treasury_stock_sync_service = providers.Factory(
        TreasuryStockSyncService,
        client=dart_company_client,
        ticker_repository=ticker_repository,
        treasury_stock_repository=stock_treasury_stock_repository,
    )
    buyback_sync_service = providers.Factory(
        BuybackSyncService,
        client=dart_company_client,
        ticker_repository=ticker_repository,
        buyback_event_repository=stock_buyback_event_repository,
    )
    buyback_service = providers.Factory(
        BuybackService,
        buyback_event_repository=stock_buyback_event_repository,
    )
    kis_income_statement_client = providers.Singleton(KisIncomeStatementClient, hantu_domestic_api)
    income_statement_sync_service = providers.Factory(
        IncomeStatementSyncService,
        database=database,
        kis_client=kis_income_statement_client,
    )
    income_statement_service = providers.Factory(
        IncomeStatementService,
        ticker_repository=ticker_repository,
        income_statement_repository=stock_income_statement_repository,
    )
    screening_service = providers.Factory(
        ScreeningService,
        ticker_repository=ticker_repository,
        fundamental_repository=stock_fundamental_repository,
        dividend_service=dividend_service,
    )
