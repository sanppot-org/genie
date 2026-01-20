"""API 스키마 정의"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.common.candle_client import CandleInterval
from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database import Ticker
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
    data_source: DataSource

    def to_entity(self) -> Ticker:
        """Ticker 엔티티로 변환"""
        return Ticker(
            ticker=self.ticker,
            asset_type=self.asset_type,
            data_source=self.data_source.value,
        )


class TickerResponse(BaseModel):
    """Ticker 응답"""

    id: int
    ticker: str
    asset_type: AssetType
    data_source: DataSource
    timezone: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_ticker(cls, ticker: Ticker) -> "TickerResponse":
        """Ticker 엔티티에서 응답 생성"""
        # DataSource는 str Enum이므로 값으로 멤버 조회
        source = DataSource(ticker.data_source)  # type: ignore[call-arg]
        return cls(
            id=ticker.id,
            ticker=ticker.ticker,
            asset_type=ticker.asset_type,
            data_source=source,
            timezone=source.timezone,
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


class QueryCandlesRequest(BaseModel):
    """캔들 조회 요청"""

    ticker_id: int
    interval: CandleInterval = CandleInterval.DAY
    count: int = 100
    end_time: datetime | None = None


class CandleData(BaseModel):
    """캔들 데이터"""

    timestamp: datetime
    local_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class QueryCandlesResponse(BaseModel):
    """캔들 조회 응답"""

    ticker_id: int
    ticker: str
    interval: CandleInterval
    count: int
    candles: list[CandleData]
