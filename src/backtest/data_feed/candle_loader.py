"""캔들 모델 → DataFrame 변환 유틸리티"""

import logging

import pandas as pd

from src.database.models import CandleBase, CandleDaily, CandleHour1, CandleMinute1, StockDailyCandle

logger = logging.getLogger(__name__)


def stock_daily_candles_to_dataframe(rows: list[StockDailyCandle]) -> tuple[pd.DataFrame, str]:
    """StockDailyCandle ORM row 리스트를 backtrader 호환 DataFrame으로 변환.

    수정주가 적용 우선순위:
      1. adj_open/adj_high/adj_low/adj_close 모두 있으면 그대로 사용.
      2. 일부만 있으면 수정계수(adj_close / close)를 open/high/low에 곱해 일관 조정. volume은 원본 사용.
      3. adj 전부 None이면 raw 사용 + WARNING 로그.

    Args:
        rows: StockDailyCandle ORM row 리스트 (세션 안에서 호출)

    Returns:
        (DataFrame, "1d") 튜플. DataFrame은 DatetimeIndex 기반 OHLCV.
    """
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([])), "1d"

    any_adj = any(r.adj_close is not None for r in rows)
    if not any_adj:
        logger.warning("StockDailyCandle: adj 컬럼이 전부 NULL — raw 주가를 사용합니다. 수정주가 백필을 권장합니다.")

    data = []
    for r in rows:
        if r.adj_open is not None and r.adj_high is not None and r.adj_low is not None and r.adj_close is not None:
            # 모든 adj 컬럼 존재: 그대로 사용
            o, h, lo, c = r.adj_open, r.adj_high, r.adj_low, r.adj_close
        elif r.adj_close is not None and r.close and r.close != 0:
            # 수정계수로 일관 조정 (adj_close 기반 비율 적용)
            ratio = r.adj_close / r.close
            o = r.open * ratio
            h = r.high * ratio
            lo = r.low * ratio
            c = r.adj_close
        else:
            # adj 없음 → raw 사용
            o, h, lo, c = r.open, r.high, r.low, r.close

        data.append({"datetime": r.date, "open": o, "high": h, "low": lo, "close": c, "volume": r.volume})

    df = pd.DataFrame(data)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    return df, "1d"


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
