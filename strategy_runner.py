#!/usr/bin/env python3
"""전략 실행 메인 진입점

지정된 전략을 실행합니다.

Usage:
    # 오전오후 전략 실행
    STRATEGY_TYPE=morning_afternoon python strategy_runner.py
    # 또는
    STRATEGY_TYPE=morning_afternoon PYTHONPATH=. uv run python strategy_runner.py

    # 변동성 돌파 전략 실행
    STRATEGY_TYPE=volatility_breakout python strategy_runner.py
    # 또는
    STRATEGY_TYPE=volatility_breakout PYTHONPATH=. uv run python strategy_runner.py

    # 기본값은 오전오후 전략
    python strategy_runner.py
"""

import logging
import os
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from src.strategy.base import BaseStrategy
from src.strategy.clock import SystemClock, Clock
from src.strategy.config import BaseStrategyConfig, StrategyType, MorningAfternoonConfig, VolatilityBreakoutConfig
from src.strategy.morning_afternoon import MorningAfternoonStrategy
from src.strategy.volatility_breakout import VolatilityBreakoutStrategy
from src.upbit.upbit_api import UpbitAPI

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


def get_strategy_type() -> StrategyType:
    """
    환경 변수에서 전략 타입을 읽어옵니다.

    Returns:
        전략 타입 (기본값: MORNING_AFTERNOON)
    """
    strategy_str = os.getenv("STRATEGY_TYPE", "morning_afternoon").lower()

    try:
        return StrategyType(strategy_str)
    except ValueError:
        logger.warning(
            f"알 수 없는 전략 타입: {strategy_str}. "
            f"기본값 'morning_afternoon'을 사용합니다."
        )
        return StrategyType.MORNING_AFTERNOON


# 이건 아무때나 호출될 수 있다.
def main():
    """메인 함수"""
    try:
        # 전략 타입 결정
        strategy_type = get_strategy_type()
        logger.info(f"전략 타입: {strategy_type.value}")

        # API 및 설정 초기화
        upbit_api = UpbitAPI()
        strategy_config = BaseStrategyConfig()

        clock = SystemClock(strategy_config.timezone)
        scheduler = BlockingScheduler(strategy_config.timezone)

        # 팩토리로 Strategy 생성
        strategy = create_strategy(strategy_type, upbit_api, strategy_config, clock, scheduler)

        # 전략 실행
        strategy.run()

    except KeyboardInterrupt:
        logger.info("사용자에 의해 종료되었습니다.")
        sys.exit(0)

    except Exception:
        logger.exception("예상치 못한 에러 발생")
        sys.exit(1)


def create_strategy(strategy_type: StrategyType, upbit: UpbitAPI, config: BaseStrategyConfig, clock: Clock,
                    scheduler: BlockingScheduler) -> BaseStrategy:
    """
    전략 타입에 따라 적절한 Strategy를 생성합니다.

    Args:
        strategy_type: 전략 타입 (MORNING_AFTERNOON 또는 VOLATILITY_BREAKOUT)
        upbit: UpbitAPI 인스턴스
        config: 전략 설정 (BaseStrategyConfig 또는 하위 클래스)
        clock: 시간 관리 객체 (None이면 SystemClock 사용)
        scheduler: APScheduler 인스턴스

    Returns:
        생성된 Strategy

    Raises:
        ValueError: 지원하지 않는 전략 타입인 경우
    """

    if strategy_type == StrategyType.MORNING_AFTERNOON:
        # MorningAfternoonConfig로 변환 (이미 MorningAfternoonConfig면 그대로 사용)
        ma_config = (
            config
            if isinstance(config, MorningAfternoonConfig)
            else MorningAfternoonConfig(**config.model_dump())
        )
        return MorningAfternoonStrategy(upbit, ma_config, clock, scheduler)

    elif strategy_type == StrategyType.VOLATILITY_BREAKOUT:
        # VolatilityBreakoutConfig로 변환 (이미 VolatilityBreakoutConfig면 그대로 사용)
        vb_config = (
            config
            if isinstance(config, VolatilityBreakoutConfig)
            else VolatilityBreakoutConfig(**config.model_dump())
        )
        return VolatilityBreakoutStrategy(upbit, vb_config, clock, scheduler)

    else:
        raise ValueError(f"지원하지 않는 전략 타입: {strategy_type}")


if __name__ == "__main__":
    main()
