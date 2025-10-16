import pandera.pandas as pa
from pandera.typing import Series


class CandleSchema(pa.DataFrameModel):
    """
    업비트 캔들 DataFrame 스키마

    pyupbit.get_ohlcv()가 반환하는 DataFrame의 스키마 정의

    Columns:
        open: 시가
        high: 고가
        low: 저가
        close: 종가
        volume: 누적 거래량
        value: 누적 거래 대금

    Index:
        DatetimeIndex: 캔들 일시
    """
    open: Series[float]
    high: Series[float]
    low: Series[float]
    close: Series[float]
    volume: Series[float]
    value: Series[float]

    class Config:
        strict = True  # 정의되지 않은 컬럼 허용 안함
        coerce = True  # 자동 타입 변환
