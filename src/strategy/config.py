"""전략 설정

전략 실행에 필요한 설정값을 관리합니다.
"""

from enum import Enum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    """전략 타입"""

    MORNING_AFTERNOON = "morning_afternoon"
    VOLATILITY_BREAKOUT = "volatility_breakout"


class BaseStrategyConfig(BaseModel):
    """
    전략 공통 설정

    Attributes:
        ticker: 거래할 티커 (예: "KRW-BTC")
        target_vol: 타겟 변동성 (0.005 ~ 0.02, 즉 0.5% ~ 2%)
        allocation_ratio: 전체 잔고 대비 전략 할당 비율 (기본 0.5 = 50%)
        min_order_amount: 최소 주문 금액 (기본 5000원)
    """

    timezone: ZoneInfo = Field(default=ZoneInfo("Asia/Seoul"), description="타임존")
    ticker: str = Field(default="KRW-BTC", description="거래할 티커")
    target_vol: float = Field(default=0.01, description="타겟 변동성 (0.5% ~ 2%)", ge=0.005, le=0.02)
    min_order_amount: float = Field(default=5000.0, description="최소 주문 금액 (KRW)", ge=5000.0)
    total_balance: float = Field(..., description="총 자산", gt=100000.0)
    allocated_balance: float = Field(..., description="할당된 금액", gt=50000.0)


class MorningAfternoonConfig(BaseStrategyConfig):
    """
    오전오후 전략 설정

    BaseStrategyConfig의 모든 설정을 상속받습니다.
    추가 전략 특화 설정이 필요하면 여기에 정의합니다.
    """

    pass


class VolatilityBreakoutConfig(BaseStrategyConfig):
    """
    변동성 돌파 전략 설정

    BaseStrategyConfig의 모든 설정을 상속받습니다.
    추가 전략 특화 설정이 필요하면 여기에 정의합니다.
    """

    pass
