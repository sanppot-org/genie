"""스케줄러 작업 컨텍스트

스케줄러 작업 실행에 필요한 의존성을 관리하는 컨텍스트 클래스
"""

import logging

from src.allocation_manager import AllocatedBalanceProvider
from src.common.clock import Clock
from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor


class ScheduledTasksContext:
    """스케줄러 작업 실행에 필요한 의존성을 관리하는 컨텍스트

    Attributes:
        allocation_manager: 잔고 할당 관리자
        slack_client: Slack 클라이언트
        healthcheck_client: 헬스체크 클라이언트
        order_executor: 주문 실행기
        clock: 시스템 시계
        data_collector: 데이터 수집기
        cache_manager: 캐시 관리자
        tickers: 거래할 티커 목록
        total_balance: 전체 잔고
        logger: 로거
    """

    def __init__(
            self,
            allocation_manager: AllocatedBalanceProvider,
            slack_client: SlackClient,
            healthcheck_client: HealthcheckClient,
            order_executor: OrderExecutor,
            clock: Clock,
            data_collector: DataCollector,
            cache_manager: CacheManager,
            tickers: list[str],
            total_balance: int,
            logger: logging.Logger,
    ) -> None:
        self.allocation_manager = allocation_manager
        self.slack_client = slack_client
        self.healthcheck_client = healthcheck_client
        self.order_executor = order_executor
        self.clock = clock
        self.data_collector = data_collector
        self.cache_manager = cache_manager
        self.tickers = tickers
        self.total_balance = total_balance
        self.logger = logger
