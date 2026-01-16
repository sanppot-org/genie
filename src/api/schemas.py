"""API 스키마 정의"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.constants import AssetType, TimeZone
from src.database import Exchange, Ticker
from src.service.candle_service import CollectMode


class SellResponse(BaseModel):
    """매도 응답 모델"""

    success: bool
    message: str
    executed_volume: float | None = None
    remaining_volume: float | None = None


class ExchangeCreate(BaseModel):
    """Exchange 생성 요청"""

    name: str
    timezone: TimeZone

    def to_entity(self) -> Exchange:
        """Exchange 엔티티로 변환"""
        return Exchange(
            name=self.name,
            timezone=self.timezone,
        )


class ExchangeUpdate(BaseModel):
    """Exchange 수정 요청"""

    name: str | None = None
    timezone: TimeZone | None = None


class ExchangeResponse(BaseModel):
    """Exchange 응답"""

    id: int
    name: str
    timezone: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_exchange(cls, exchange: Exchange) -> "ExchangeResponse":
        """Exchange 엔티티에서 응답 생성"""
        return cls(
            id=exchange.id,
            name=exchange.name,
            timezone=exchange.timezone,
        )


class TickerCreate(BaseModel):
    """Ticker 생성 요청"""

    ticker: str
    asset_type: AssetType
    exchange_id: int

    def to_entity(self) -> Ticker:
        """Ticker 엔티티로 변환"""
        return Ticker(
            ticker=self.ticker,
            asset_type=self.asset_type,
            exchange_id=self.exchange_id,
        )


class TickerResponse(BaseModel):
    """Ticker 응답"""

    id: int
    ticker: str
    asset_type: AssetType
    exchange_id: int
    exchange_name: str | None = None
    timezone: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_ticker(cls, ticker: Ticker) -> "TickerResponse":
        """Ticker 엔티티에서 응답 생성"""
        return cls(
            id=ticker.id,
            ticker=ticker.ticker,
            asset_type=ticker.asset_type,
            exchange_id=ticker.exchange_id,
            exchange_name=ticker.exchange.name if ticker.exchange else None,
            timezone=ticker.exchange.timezone if ticker.exchange else None,
        )


class GenieResponse[T](BaseModel):
    """공통 API 응답 모델"""

    data: T

    model_config = ConfigDict(from_attributes=True)


class CollectCandlesRequest(BaseModel):
    """1분봉 수집 요청"""

    ticker_id: int
    to: datetime | None = None
    start: datetime | None = None
    batch_size: int = 1000
    mode: CollectMode = CollectMode.INCREMENTAL


class CollectCandlesResponse(BaseModel):
    """1분봉 수집 응답"""

    total_saved: int
    ticker_id: int
    ticker: str
    mode: CollectMode
