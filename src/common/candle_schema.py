"""공통 캔들 DataFrame 스키마 정의."""

from datetime import datetime

import pandera.pandas as pa
from pandera.typing import Series


class CommonCandleSchema(pa.DataFrameModel):
    """공통 캔들 DataFrame 스키마.

    모든 거래소(Upbit, Binance, Hantu 등)에서 공통으로 사용하는
    캔들 데이터의 스키마입니다.

    Columns:
        timestamp: UTC 시간
        local_time: 로컬 시간 (KST 등)
        open: 시가
        high: 고가
        low: 저가
        close: 종가
        volume: 거래량

    Index:
        DatetimeIndex: UTC timezone-aware

    Example:
        >>> import pandas as pd
        >>> from datetime import datetime, UTC
        >>> df = pd.DataFrame({
        ...     "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
        ...     "local_time": [datetime(2024, 1, 1, 9, 0, 0)],
        ...     "open": [100.0],
        ...     "high": [105.0],
        ...     "low": [99.0],
        ...     "close": [104.0],
        ...     "volume": [1000.0],
        ... }, index=pd.DatetimeIndex([datetime(2024, 1, 1, tzinfo=UTC)]))
        >>> validated = CommonCandleSchema.validate(df)
    """

    timestamp: Series[datetime]
    local_time: Series[datetime]
    open: Series[float]
    high: Series[float]
    low: Series[float]
    close: Series[float]
    volume: Series[float]

    class Config:
        strict = True  # 정의되지 않은 컬럼 허용 안함
        coerce = True  # 자동 타입 변환
