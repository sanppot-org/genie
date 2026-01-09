"""API 스키마 정의"""
from pydantic import BaseModel, ConfigDict


class SellResponse(BaseModel):
    """매도 응답 모델"""

    success: bool
    message: str
    executed_volume: float | None = None
    remaining_volume: float | None = None


class TickerCreate(BaseModel):
    """Ticker 생성 요청"""

    ticker: str
    asset_type: str


class TickerResponse(BaseModel):
    """Ticker 응답"""

    id: int
    ticker: str
    asset_type: str

    model_config = ConfigDict(from_attributes=True)


class GenieResponse[T](BaseModel):
    """공통 API 응답 모델"""

    data: T

    model_config = ConfigDict(from_attributes=True)
