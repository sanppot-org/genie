"""Tests for PykrxFundamentalClient."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest
from tenacity import wait_none

from src.providers.pykrx_fundamental_client import (
    PykrxFundamentalClient,
    PykrxFundamentalSnapshot,
)
from src.providers.pykrx_ticker_client import EmptyPykrxResponseError


def _df(rows: dict[str, dict[str, float]]) -> pd.DataFrame:
    """{ticker: {BPS: ..., PER: ..., ...}} → DataFrame indexed by ticker."""
    return pd.DataFrame.from_dict(rows, orient="index")


class TestPykrxFundamentalClient:
    """PykrxFundamentalClient 단위 테스트."""

    def test_fetch_by_date_returns_snapshot_list(self) -> None:
        """정상 응답을 frozen dataclass 리스트로 변환."""
        df = _df({
            "005930": {"BPS": 50000, "PER": 12.5, "PBR": 1.4, "EPS": 4000, "DIV": 2.5, "DPS": 1250},
            "000660": {"BPS": 80000, "PER": 8.0, "PBR": 1.1, "EPS": 10000, "DIV": 1.5, "DPS": 1200},
        })
        client = PykrxFundamentalClient()
        with patch("src.providers.pykrx_fundamental_client.stock.get_market_fundamental", return_value=df):
            result = client.fetch_by_date(date(2024, 1, 2))

        assert len(result) == 2
        by_ticker = {s.ticker: s for s in result}
        assert by_ticker["005930"] == PykrxFundamentalSnapshot(
            ticker="005930", bps=50000.0, per=12.5, pbr=1.4, eps=4000.0, div=2.5, dps=1250.0,
        )

    def test_fetch_by_date_raises_on_empty_response(self) -> None:
        """빈 DataFrame → 재시도 후 EmptyPykrxResponseError 전파."""
        client = PykrxFundamentalClient()
        # 테스트 속도 위해 wait 제거
        client.fetch_by_date.retry.wait = wait_none()  # type: ignore[attr-defined]

        with patch(
            "src.providers.pykrx_fundamental_client.stock.get_market_fundamental",
            return_value=pd.DataFrame(),
        ), pytest.raises(EmptyPykrxResponseError):
            client.fetch_by_date(date(2024, 1, 1))

    def test_nan_values_become_none(self) -> None:
        """적자/빈 셀(NaN)은 snapshot 필드에서 None으로 정규화."""
        df = _df({
            "999999": {"BPS": float("nan"), "PER": float("nan"), "PBR": 1.0,
                       "EPS": float("nan"), "DIV": 0.0, "DPS": 0.0},
        })
        client = PykrxFundamentalClient()
        with patch("src.providers.pykrx_fundamental_client.stock.get_market_fundamental", return_value=df):
            result = client.fetch_by_date(date(2024, 1, 2))

        assert result[0] == PykrxFundamentalSnapshot(
            ticker="999999", bps=None, per=None, pbr=1.0, eps=None, div=0.0, dps=0.0,
        )
