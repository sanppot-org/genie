"""UsStockDailyClient 테스트 (FDR/yfinance mock)."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from src.providers.us_stock_daily_client import UsDailyBar, UsStockDailyClient


def _fdr_df() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {
            "Open": [187.15, 184.22],
            "High": [188.44, 185.88],
            "Low": [183.89, 183.43],
            "Close": [185.64, 184.25],
            "Volume": [82488700, 58414500],
            "Adj Close": [183.56, 182.19],
        },
        index=idx,
    )


def test_fetch_uses_fdr_and_normalizes() -> None:
    client = UsStockDailyClient()
    with patch("src.providers.us_stock_daily_client.fdr.DataReader", return_value=_fdr_df()) as m:
        bars = client.fetch("AAPL", date(2024, 1, 1), date(2024, 1, 10))
    m.assert_called_once()
    assert bars == [
        UsDailyBar(date=date(2024, 1, 2), open=187.15, high=188.44, low=183.89,
                   close=185.64, volume=82488700, adj_close=183.56),
        UsDailyBar(date=date(2024, 1, 3), open=184.22, high=185.88, low=183.43,
                   close=184.25, volume=58414500, adj_close=182.19),
    ]


def test_fetch_falls_back_to_yfinance_on_fdr_failure() -> None:
    client = UsStockDailyClient()
    yf_df = _fdr_df()  # 동일 컬럼 형태 (auto_adjust=False 시 Adj Close 포함)
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = yf_df
    with patch("src.providers.us_stock_daily_client.fdr.DataReader", side_effect=RuntimeError("boom")), \
         patch("src.providers.us_stock_daily_client.yf.Ticker", return_value=fake_ticker):
        bars = client.fetch("AAPL", date(2024, 1, 1), date(2024, 1, 10))
    assert len(bars) == 2
    assert bars[0].close == 185.64


def test_fetch_returns_empty_when_fdr_empty() -> None:
    client = UsStockDailyClient()
    with patch("src.providers.us_stock_daily_client.fdr.DataReader", return_value=pd.DataFrame()), \
         patch("src.providers.us_stock_daily_client.yf.Ticker", return_value=MagicMock(history=MagicMock(return_value=pd.DataFrame()))):
        bars = client.fetch("ZZZZ", date(2024, 1, 1), date(2024, 1, 10))
    assert bars == []
