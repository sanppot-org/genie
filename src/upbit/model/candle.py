from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Union

import pandas as pd

from src import constants as const


@dataclass
class CandleData:
    """
    업비트 캔들 데이터

    캔들(OHLCV) 시세 정보를 나타냅니다. 모든 가격 필드는 정밀도 보존을 위해 문자열로 제공됩니다.

    Attributes:
        open: 시가 (문자열)
        high: 고가 (문자열)
        low: 저가 (문자열)
        close: 종가 (문자열)
        volume: 누적 거래량 (문자열)
        value: 누적 거래 대금 (문자열)
    """
    open: float
    high: float
    low: float
    close: float
    volume: float
    value: float

    @classmethod
    def from_dataframe_row(cls, row: Union[pd.Series, Mapping[str, Any]]) -> "CandleData":
        """
        pyupbit DataFrame의 row로부터 CandleData 생성
        
        Args:
            row: OHLCV 데이터를 포함한 pandas Series
                 (columns: open, high, low, close, volume, value)
        
        Returns:
            CandleData 인스턴스
        """
        return cls(
            open=float(row[const.FIELD_OPEN]),
            high=float(row[const.FIELD_HIGH]),
            low=float(row[const.FIELD_LOW]),
            close=float(row[const.FIELD_CLOSE]),
            volume=float(row[const.FIELD_VOLUME]),
            value=float(row[const.FIELD_VALUE]),
        )
