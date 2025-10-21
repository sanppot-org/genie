from zoneinfo import ZoneInfo

from src.common.clock import SystemClock
from src.common.google_sheet.client import GoogleSheetClient
from src.common.slack.client import SlackClient
from src.config import GoogleSheetConfig, SlackConfig, UpbitConfig
from src.constants import KST, RESERVED_BALANCE
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.morning_afternoon_strategy import MorningAfternoonStrategy
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.volatility_strategy import VolatilityStrategy
from src.upbit.upbit_api import UpbitAPI


def run(ticker: str, total_balance: float, allocated_balance: float, target_vol: float = 0.01, timezone: ZoneInfo = KST) -> None:
    # 공유 컴포넌트
    clock = SystemClock(timezone)
    data_collector = DataCollector(clock)
    google_sheet_client = GoogleSheetClient(GoogleSheetConfig())
    slack_client = SlackClient(SlackConfig())
    upbit_api = UpbitAPI(UpbitConfig())  # type: ignore
    order_executor = OrderExecutor(upbit_api, google_sheet_client=google_sheet_client, slack_client=slack_client)
    cache_manager = CacheManager()

    allocated_balance_per_strategy = (allocated_balance - RESERVED_BALANCE) / 2  # 티커에 할당된 금액을 전략별로 5:5로 나눈다.
    strategy_config = BaseStrategyConfig(timezone=timezone, ticker=ticker, target_vol=target_vol, total_balance=total_balance, allocated_balance=allocated_balance_per_strategy)

    volatility_strategy = VolatilityStrategy(order_executor, strategy_config, clock, data_collector, cache_manager)
    morning_afternoon_strategy = MorningAfternoonStrategy(order_executor, strategy_config, clock, data_collector, cache_manager)

    try:
        volatility_strategy.execute()
    except Exception as e:
        slack_client.send_status(f"{ticker} 변동성 돌파 전략 에러 발생. log: {e}")

    try:
        morning_afternoon_strategy.execute()
    except Exception as e:
        slack_client.send_status(f"{ticker} 오전 오후 전략 에러 발생. log: {e}")
