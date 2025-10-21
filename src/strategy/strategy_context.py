from dataclasses import dataclass

from src.common.clock import SystemClock
from src.common.google_sheet.client import GoogleSheetClient
from src.common.slack.client import SlackClient
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.upbit.upbit_api import UpbitAPI


@dataclass
class StrategyContext:
    """전략 실행에 필요한 공유 컴포넌트들을 담는 컨테이너"""

    clock: SystemClock
    data_collector: DataCollector
    google_sheet_client: GoogleSheetClient
    slack_client: SlackClient
    upbit_api: UpbitAPI
    order_executor: OrderExecutor
    cache_manager: CacheManager
