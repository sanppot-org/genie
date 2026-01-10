"""API 스키마 정의"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.constants import AssetType
from src.service.candle_service import CollectMode


class SellResponse(BaseModel):
    """매도 응답 모델"""

    success: bool
    message: str
    executed_volume: float | None = None
    remaining_volume: float | None = None


class TickerCreate(BaseModel):
    """Ticker 생성 요청"""

    ticker: str
    asset_type: AssetType


class TickerResponse(BaseModel):
    """Ticker 응답"""

    id: int
    ticker: str
    asset_type: AssetType

    model_config = ConfigDict(from_attributes=True)


class GenieResponse[T](BaseModel):
    """공통 API 응답 모델"""

    data: T

    model_config = ConfigDict(from_attributes=True)


class CollectCandlesRequest(BaseModel):
    """1분봉 수집 요청"""

    ticker_id: int
    to: datetime | None = None
    batch_size: int = 1000
    mode: CollectMode = CollectMode.INCREMENTAL


class CollectCandlesResponse(BaseModel):
    """1분봉 수집 응답"""

    total_saved: int
    ticker_id: int
    ticker: str
    mode: CollectMode
