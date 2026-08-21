"""Tests for PykrxDailyCandleClient (수정주가 종목별 조회)."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest
from tenacity import wait_none

from src.providers.pykrx_daily_candle_client import PykrxAdjustedCandle, PykrxDailyCandleClient
from src.providers.pykrx_ticker_client import EmptyPykrxResponseError


def _ohlcv(rows: dict[str, tuple[float, float, float, float, int]]) -> pd.DataFrame:
    """{'YYYYMMDD': (시,고,저,종,거래량)} → DatetimeIndex DataFrame."""
    idx = pd.to_datetime(list(rows.keys()))
    data = list(rows.values())
    return pd.DataFrame(
        {
            "시가": [r[0] for r in data],
            "고가": [r[1] for r in data],
            "저가": [r[2] for r in data],
            "종가": [r[3] for r in data],
            "거래량": [r[4] for r in data],
        },
        index=idx,
    )


class TestFetchAdjustedByTicker:
    def test_정상_수정주가_변환(self) -> None:
        df = _ohlcv({
            "20180426": (52000, 52200, 51800, 52140, 360931),
            "20180504": (53000, 53900, 51800, 51900, 39565391),
        })
        client = PykrxDailyCandleClient()
        with patch(
            "src.providers.pykrx_daily_candle_client.stock.get_market_ohlcv_by_date",
            return_value=df,
        ):
            result = client.fetch_adjusted_by_ticker("005930", date(2018, 4, 26), date(2018, 5, 4))

        assert result == [
            PykrxAdjustedCandle(date=date(2018, 4, 26), open=52000, high=52200, low=51800, close=52140, volume=360931),
            PykrxAdjustedCandle(date=date(2018, 5, 4), open=53000, high=53900, low=51800, close=51900, volume=39565391),
        ]

    def test_거래정지_0값_row_스킵(self) -> None:
        """액면분할 준비 거래정지(OHLV·거래량 0) row는 제외한다."""
        df = _ohlcv({
            "20180427": (53380, 53639, 52440, 53000, 606216),
            "20180430": (0, 0, 0, 53000, 0),  # 거래정지
            "20180503": (0, 0, 0, 53000, 0),  # 거래정지
            "20180504": (53000, 53900, 51800, 51900, 39565391),
        })
        client = PykrxDailyCandleClient()
        with patch(
            "src.providers.pykrx_daily_candle_client.stock.get_market_ohlcv_by_date",
            return_value=df,
        ):
            result = client.fetch_adjusted_by_ticker("005930", date(2018, 4, 27), date(2018, 5, 4))

        assert [c.date for c in result] == [date(2018, 4, 27), date(2018, 5, 4)]

    def test_빈_응답_재시도후_에러(self) -> None:
        client = PykrxDailyCandleClient()
        client.fetch_adjusted_by_ticker.retry.wait = wait_none()  # type: ignore[attr-defined]
        with patch(
            "src.providers.pykrx_daily_candle_client.stock.get_market_ohlcv_by_date",
            return_value=pd.DataFrame(),
        ), pytest.raises(EmptyPykrxResponseError):
            client.fetch_adjusted_by_ticker("005930", date(2018, 1, 1), date(2018, 1, 2))


class TestFetchByDate:
    def test_pykrx_컬럼누락_key_error_재시도후_빈응답에러(self) -> None:
        """pykrx 내부의 예상 OHLCV 컬럼 누락도 빈 응답으로 정규화해 재시도한다."""
        original_wait = PykrxDailyCandleClient.fetch_by_date.retry.wait  # type: ignore[attr-defined]
        PykrxDailyCandleClient.fetch_by_date.retry.wait = wait_none()  # type: ignore[attr-defined]
        try:
            with patch(
                "src.providers.pykrx_daily_candle_client.stock.get_market_ohlcv",
                side_effect=KeyError("None of [Index(['시가', '고가'])] are in the [columns]"),
            ) as mocked:
                with pytest.raises(EmptyPykrxResponseError) as exc_info:
                    PykrxDailyCandleClient().fetch_by_date(date(2026, 8, 21))

            assert mocked.call_count == 3
            assert isinstance(exc_info.value.__cause__, KeyError)
        finally:
            PykrxDailyCandleClient.fetch_by_date.retry.wait = original_wait  # type: ignore[attr-defined]
