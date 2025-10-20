"""캐시 모델

전략에서 사용하는 캐시 데이터 모델을 정의합니다.
"""

import datetime as dt

from pydantic import BaseModel, Field

from src.strategy.data.models import Recent20DaysHalfDayCandles


class DataCache(BaseModel):
    """DataCollector가 관리하는 영구 캐시

    API 호출로 수집한 캔들 데이터를 파일로 저장합니다.

    Attributes:
        ticker: 종목 코드 (예: KRW-BTC)
        last_update_date: 마지막 업데이트 날짜
        history: 최근 20일의 반일봉 데이터
    """

    ticker: str = Field(..., description="종목 코드")
    last_update_date: dt.date = Field(..., description="마지막 업데이트 날짜")
    history: Recent20DaysHalfDayCandles = Field(..., description="최근 20일의 반일봉 데이터")


class StrategyCacheData(BaseModel):
    """각 전략이 독립적으로 관리하는 캐시

    전략별 실행 상태를 개별 파일로 저장합니다.

    Attributes:
        execution_volume: 체결 수량
        last_run_date: 마지막 실행 날짜
    """

    execution_volume: float = Field(default=0.0, description="체결 수량")
    last_run_date: dt.date = Field(..., description="마지막 실행 날짜")

    def has_position(self, today: dt.date) -> bool:
        """오늘 포지션이 있는지 확인

        Args:
            today: 오늘 날짜

        Returns:
            오늘 날짜이고 체결 수량이 있으면 True, 아니면 False
        """
        return self.last_run_date == today and self.execution_volume > 0


class VolatilityStrategyCacheData(StrategyCacheData):
    """변동성 전략 전용 캐시

    변동성 전략에서 계산한 매수 비중과 돌파 가격을 저장합니다.

    Attributes:
        position_size: 매수 비중 (0~1)
        threshold: 돌파 가격
    """

    position_size: float = Field(..., description="매수 비중 (0~1)")
    threshold: float = Field(..., description="돌파 가격")
