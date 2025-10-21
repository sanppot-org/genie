from zoneinfo import ZoneInfo

from src.constants import KST, RESERVED_BALANCE
from src.strategy.config import BaseStrategyConfig
from src.strategy.morning_afternoon_strategy import MorningAfternoonStrategy
from src.strategy.strategy_context import StrategyContext
from src.strategy.volatility_strategy import VolatilityStrategy


def run(ticker: str, total_balance: float, allocated_balance: float, context: StrategyContext, target_vol: float = 0.01, timezone: ZoneInfo = KST) -> None:
    """전략 실행 함수

    Args:
        ticker: 거래할 티커 (예: KRW-BTC)
        total_balance: 전체 잔고
        allocated_balance: 티커에 할당된 금액
        context: 재사용 가능한 공유 컴포넌트들
        target_vol: 목표 변동성 (기본값: 0.01)
        timezone: 시간대 (기본값: KST)
    """
    allocated_balance_per_strategy = (allocated_balance - RESERVED_BALANCE) / 2  # 티커에 할당된 금액을 전략별로 5:5로 나눈다.
    strategy_config = BaseStrategyConfig(timezone=timezone, ticker=ticker, target_vol=target_vol, total_balance=total_balance, allocated_balance=allocated_balance_per_strategy)

    # TODO: 한 번만 생성하기?
    volatility_strategy = VolatilityStrategy(context.order_executor, strategy_config, context.clock, context.data_collector, context.cache_manager)
    morning_afternoon_strategy = MorningAfternoonStrategy(context.order_executor, strategy_config, context.clock, context.data_collector, context.cache_manager)

    try:
        volatility_strategy.execute()
    except Exception as e:
        context.slack_client.send_status(f"{ticker} 변동성 돌파 전략 에러 발생. log: {e}")

    try:
        morning_afternoon_strategy.execute()
    except Exception as e:
        context.slack_client.send_status(f"{ticker} 오전 오후 전략 에러 발생. log: {e}")
