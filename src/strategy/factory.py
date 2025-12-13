"""전략 팩토리 모듈"""

from dependency_injector.wiring import Provide, inject

from src.common.clock import Clock
from src.container import ApplicationContainer
from src.scheduled_tasks.context import ScheduledTasksContext
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.config import VolatilityBreakoutConfig
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.strategy.volatility_strategy import VolatilityStrategy


@inject
def create_volatility_strategy(
        ticker: str,
        tasks_ctx: ScheduledTasksContext = Provide[ApplicationContainer.tasks_context],
        order_executor: OrderExecutor = Provide[ApplicationContainer.order_executor],
        clock: Clock = Provide[ApplicationContainer.clock],
        data_collector: DataCollector = Provide[ApplicationContainer.data_collector],
        cache_manager: CacheManager = Provide[ApplicationContainer.cache_manager],
) -> VolatilityStrategy:
    """VolatilityStrategy 인스턴스를 생성합니다.

    Args:
        ticker: 거래 티커 (예: "KRW-BTC")
        tasks_ctx: 스케줄 작업 컨텍스트 (자동 주입)
        order_executor: 주문 실행기 (자동 주입)
        clock: 시계 (자동 주입)
        data_collector: 데이터 수집기 (자동 주입)
        cache_manager: 캐시 관리자 (자동 주입)

    Returns:
        VolatilityStrategy 인스턴스
    """
    # ticker별 할당 금액 계산 (균등 분배)
    total_balance = tasks_ctx.total_balance
    num_tickers = len(tasks_ctx.tickers)
    allocated_balance = total_balance / num_tickers

    # VolatilityBreakoutConfig 생성
    config = VolatilityBreakoutConfig(
        ticker=ticker,
        total_balance=total_balance,
        allocated_balance=allocated_balance,
    )

    # VolatilityStrategy 생성
    return VolatilityStrategy(
        order_executor=order_executor,
        clock=clock,
        collector=data_collector,
        cache_manager=cache_manager,
        config=config,
    )
