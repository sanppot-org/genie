"""바이낸스 API 클라이언트."""

from datetime import datetime
from typing import Optional

import requests

from util.binance.model.candle import BinanceCandleData, BinanceCandleInterval


class BinanceAPI:
    """바이낸스 API 클라이언트.
    
    공개 API를 사용하여 시세 정보를 조회합니다.
    """

    BASE_URL = "https://api.binance.com"

    def __init__(self) -> None:
        """BinanceAPI 초기화."""
        self.session = requests.Session()

    def get_candles(
            self,
            symbol: str,
            interval: BinanceCandleInterval,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
            limit: int = 500,
    ) -> list[BinanceCandleData]:
        """캔들 데이터 조회.
        
        Args:
            symbol: 심볼 (예: "BTCUSDT")
            interval: 캔들 간격
            start_time: 시작 시간 (선택)
            end_time: 종료 시간 (선택)
            limit: 최대 개수 (기본: 500, 최대: 1000)
        
        Returns:
            캔들 데이터 리스트
        
        Raises:
            requests.HTTPError: API 요청 실패
        """
        url = f"{self.BASE_URL}/api/v3/klines"

        params: dict[str, str | int] = {
            "symbol": symbol,
            "interval": interval.value,
            "limit": limit,
        }

        if start_time:
            params["startTime"] = int(start_time.timestamp() * 1000)

        if end_time:
            params["endTime"] = int(end_time.timestamp() * 1000)

        response = self.session.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        return [BinanceCandleData.from_api_response(item) for item in data]


def get_candles(
        symbol: str = "BTCUSDT",
        interval: BinanceCandleInterval = BinanceCandleInterval.MINUTE_1,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
) -> list[BinanceCandleData]:
    """캔들 데이터 조회 (편의 함수).
    
    Args:
        symbol: 심볼 (기본: "BTCUSDT")
        interval: 캔들 간격 (기본: 1분)
        start_time: 시작 시간 (선택)
        end_time: 종료 시간 (선택)
        limit: 최대 개수 (기본: 500, 최대: 1000)
    
    Returns:
        캔들 데이터 리스트
    
    Example:
        >>> from datetime import datetime, timedelta
        >>> from src.binance.binance_api import get_candles
        >>> from src.binance.model.candle import BinanceCandleInterval
        >>> 
        >>> # 최근 100개의 1분봉 조회
        >>> candles = get_candles(symbol="BTCUSDT", interval=BinanceCandleInterval.MINUTE_1, limit=100)
        >>> 
        >>> # 특정 기간의 1시간봉 조회
        >>> end = datetime.now()
        >>> start = end - timedelta(days=7)
        >>> candles = get_candles(
        ...     symbol="ETHUSDT",
        ...     interval=BinanceCandleInterval.HOUR_1,
        ...     start_time=start,
        ...     end_time=end
        ... )
    """
    api = BinanceAPI()
    return api.get_candles(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
