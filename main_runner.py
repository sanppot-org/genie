import logging
from zoneinfo import ZoneInfo

from src.config import UpbitConfig
from src.constants import KST
from src.strategy.cache_manager import CacheManager
from src.strategy.clock import SystemClock
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.morning_afternoon_strategy import MorningAfternoonStrategy
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.volatility_strategy import VolatilityStrategy
from src.upbit.upbit_api import UpbitAPI

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

total_balance = 100_000_000
allocated_balance = 2_000_000


def run(ticker: str, total_balance: float, allocated_balance: float, target_vol: float = 0.01, timezone: ZoneInfo = KST) -> None:
    # 공유 컴포넌트
    clock = SystemClock(timezone)
    data_collector = DataCollector(clock)
    upbit_api = UpbitAPI(UpbitConfig())  # type: ignore
    order_executor = OrderExecutor(upbit_api)
    cache_manager = CacheManager()

    allocated_balance_per_strategy = (allocated_balance - 100) / 2  # 티커에 할당된 금액을 전략별로 5:5로 나눈다.
    strategy_config = BaseStrategyConfig(timezone=timezone, ticker=ticker, target_vol=target_vol, total_balance=total_balance, allocated_balance=allocated_balance_per_strategy)

    volatility_strategy = VolatilityStrategy(order_executor, strategy_config, clock, data_collector, cache_manager)
    morning_afternoon_strategy = MorningAfternoonStrategy(order_executor, strategy_config, clock, data_collector, cache_manager)

    volatility_strategy.execute()
    morning_afternoon_strategy.execute()


if __name__ == "__main__":
    run(ticker="KRW-BTC", total_balance=total_balance, allocated_balance=allocated_balance)
    run(ticker="KRW-ETH", total_balance=total_balance, allocated_balance=allocated_balance)
