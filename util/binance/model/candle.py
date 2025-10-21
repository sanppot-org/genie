"""바이낸스 캔들 데이터 모델."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BinanceCandleInterval(str, Enum):
    """바이낸스 캔들 간격."""

    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_8 = "8h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    DAY_3 = "3d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class BinanceCandleData(BaseModel):
    """바이낸스 캔들 데이터.
    
    Attributes:
        open_time: 캔들 시작 시간
        open_price: 시가
        high_price: 고가
        low_price: 저가
        close_price: 종가
        volume: 거래량
        close_time: 캔들 종료 시간
        quote_asset_volume: Quote 자산 거래량
        number_of_trades: 거래 건수
        taker_buy_base_volume: Taker 매수 Base 자산 거래량
        taker_buy_quote_volume: Taker 매수 Quote 자산 거래량
    """

    open_time: datetime = Field(..., description="캔들 시작 시간")
    open_price: float = Field(..., description="시가")
    high_price: float = Field(..., description="고가")
    low_price: float = Field(..., description="저가")
    close_price: float = Field(..., description="종가")
    volume: float = Field(..., description="거래량")
    close_time: datetime = Field(..., description="캔들 종료 시간")
    quote_asset_volume: float = Field(..., description="Quote 자산 거래량")
    number_of_trades: int = Field(..., description="거래 건수")
    taker_buy_base_volume: float = Field(..., description="Taker 매수 Base 자산 거래량")
    taker_buy_quote_volume: float = Field(..., description="Taker 매수 Quote 자산 거래량")

    @field_validator("open_price", "high_price", "low_price", "close_price", mode="before")
    @classmethod
    def convert_price_to_float(cls, v: Any) -> float:
        """문자열 가격을 float으로 변환."""
        if isinstance(v, str):
            return float(v)
        return v

    @field_validator("volume", "quote_asset_volume", "taker_buy_base_volume", "taker_buy_quote_volume", mode="before")
    @classmethod
    def convert_volume_to_float(cls, v: Any) -> float:
        """문자열 거래량을 float으로 변환."""
        if isinstance(v, str):
            return float(v)
        return v

    @field_validator("open_time", "close_time", mode="before")
    @classmethod
    def convert_timestamp_to_datetime(cls, v: Any) -> datetime:
        """밀리초 타임스탬프를 datetime으로 변환."""
        if isinstance(v, int):
            return datetime.fromtimestamp(v / 1000, tz=timezone.utc)
        return v

    @classmethod
    def from_api_response(cls, data: list[Any]) -> "BinanceCandleData":
        """바이낸스 API 응답을 BinanceCandleData로 변환.
        
        Args:
            data: 바이낸스 API 응답 (리스트 형태)
                [
                    open_time,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    close_time,
                    quote_asset_volume,
                    number_of_trades,
                    taker_buy_base_volume,
                    taker_buy_quote_volume,
                    ignore
                ]
        
        Returns:
            BinanceCandleData 객체
        """
        return cls(
            open_time=data[0],
            open_price=data[1],
            high_price=data[2],
            low_price=data[3],
            close_price=data[4],
            volume=data[5],
            close_time=data[6],
            quote_asset_volume=data[7],
            number_of_trades=data[8],
            taker_buy_base_volume=data[9],
            taker_buy_quote_volume=data[10],
        )
