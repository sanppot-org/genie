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


class StrategyCache(BaseModel):
    """Strategy가 관리하는 영구 캐시

    전략 실행 상태와 계산 결과를 파일로 저장합니다.

    Attributes:
        ticker: 종목 코드 (예: KRW-BTC)
        last_run_date: 마지막 실행 날짜
        volatility_position_size: 변동성 돌파 전략 매수 비중
        volatility_threshold: 변동성 돌파 가격
        volatility_execution_volume: 변동성 돌파 매수 체결 수량
        morning_afternoon_execution_volume: 오전오후 전략 매수 체결 수량
    """

    ticker: str = Field(..., description="종목 코드")
    last_run_date: dt.date = Field(..., description="마지막 실행 날짜")
    volatility_position_size: float = Field(..., description="변동성 돌파 전략 매수 비중")
    volatility_threshold: float = Field(default=float("inf"), description="변동성 돌파 가격")
    volatility_execution_volume: float = Field(default=0.0, description="변동성 돌파 매수 체결 수량")
    morning_afternoon_execution_volume: float = Field(default=0.0, description="오전오후 전략 매수 체결 수량")
