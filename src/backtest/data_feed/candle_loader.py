"""캔들 모델 → DataFrame 변환 유틸리티"""

import pandas as pd

from src.database.models import CandleBase, CandleDaily, CandleHour1, CandleMinute1


def candles_to_dataframe(
        candles: list[CandleBase],
) -> tuple[pd.DataFrame, str]:
    """캔들 리스트를 backtrader 호환 DataFrame으로 변환

    모든 캔들 모델(CandleMinute1, CandleHour1, CandleDaily)을 지원합니다.

    Args:
        candles: 캔들 리스트 (CandleMinute1, CandleHour1, CandleDaily)

    Returns:
        (DataFrame, timeframe) 튜플
        - DataFrame: DatetimeIndex를 가진 OHLCV DataFrame
        - timeframe: "1m", "1h", "1d"

    Example:
        >>> # 일봉
        >>> candles = daily_repo.get_candles(ticker_id=1, ...)
        >>> df, timeframe = candles_to_dataframe(candles)
        >>> # timeframe == "1d"

        >>> # 1분봉
        >>> candles = minute_repo.get_candles(ticker_id=1, ...)
        >>> df, timeframe = candles_to_dataframe(candles)
        >>> # timeframe == "1m"
    """
    if not candles:
        return pd.DataFrame(
            columns=['open', 'high', 'low', 'close', 'volume'],
            index=pd.DatetimeIndex([])
        ), "unknown"

    # 캔들 타입 감지
    candle = candles[0]
    if isinstance(candle, CandleDaily):
        time_field = 'date'
        timeframe = "1d"
    elif isinstance(candle, CandleMinute1):
        time_field = 'local_time'
        timeframe = "1m"
    elif isinstance(candle, CandleHour1):
        time_field = 'local_time'
        timeframe = "1h"
    else:
        # 기본값: local_time 시도
        time_field = 'local_time' if hasattr(candle, 'local_time') else 'date'
        timeframe = "unknown"

    # DataFrame 생성
    data = []
    for c in candles:
        data.append({
            'datetime': getattr(c, time_field),
            'open': c.open,
            'high': c.high,
            'low': c.low,
            'close': c.close,
            'volume': c.volume,
        })

    df = pd.DataFrame(data)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)

    return df, timeframe


def timeframe_to_korean(timeframe: str) -> str:
    """타임프레임 코드를 한글로 변환

    Args:
        timeframe: "1m", "1h", "1d", "unknown"

    Returns:
        한글 타임프레임 문자열
    """
    mapping = {
        "1m": "1분봉 (1 Minute)",
        "1h": "1시간봉 (1 Hour)",
        "1d": "일봉 (Daily)",
        "unknown": "알 수 없음",
    }
    return mapping.get(timeframe, timeframe)
