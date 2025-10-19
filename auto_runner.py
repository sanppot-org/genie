from zoneinfo import ZoneInfo

from src.config import UpbitConfig
from src.constants import KST
from src.strategy.clock import SystemClock
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.strategy import TradingService
from src.upbit.upbit_api import UpbitAPI


def run(ticker: str, total_balance: float, allocated_balance: float, target_vol: float = 0.01, timezone: ZoneInfo = KST) -> None:
    strategy_config = BaseStrategyConfig(timezone=timezone, ticker=ticker, target_vol=target_vol, total_balance=total_balance, allocated_balance=allocated_balance)

    clock = SystemClock(strategy_config.timezone)
    data_collector = DataCollector(clock)

    upbit_api = UpbitAPI(UpbitConfig())  # type: ignore
    order_executor = OrderExecutor(upbit_api)

    trading_service = TradingService(order_executor, strategy_config, clock, data_collector)
    trading_service.run()
