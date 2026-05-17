"""Tests for FundamentalService (읽기 전용)."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.database.models import StockFundamental, Ticker
from src.service.exceptions import GenieError
from src.service.fundamental_service import FundamentalService


class TestFundamentalServiceGetTimeSeries:
    """get_time_series — ticker 코드 → 시계열 변환."""

    def test_정상_조회(self) -> None:
        """ticker 발견 + repository 시계열 반환."""
        ticker_repo = MagicMock()
        fundamental_repo = MagicMock()
        ticker = MagicMock(spec=Ticker, id=1, ticker="005930", name="삼성전자")
        rows = [
            MagicMock(spec=StockFundamental, date=date(2024, 1, 2), per=12.5),
            MagicMock(spec=StockFundamental, date=date(2024, 1, 3), per=12.8),
        ]
        ticker_repo.find_by_ticker.return_value = ticker
        fundamental_repo.find_by_ticker.return_value = rows

        service = FundamentalService(ticker_repo, fundamental_repo)
        result_ticker, result_rows = service.get_time_series(
            "005930", date(2024, 1, 1), date(2024, 1, 31),
        )

        assert result_ticker is ticker
        assert result_rows == rows
        ticker_repo.find_by_ticker.assert_called_once_with("005930")
        fundamental_repo.find_by_ticker.assert_called_once_with(1, date(2024, 1, 1), date(2024, 1, 31))

    def test_미발견_종목은_GenieError(self) -> None:
        """ticker 코드 미발견 시 GenieError (NOT_FOUND)."""
        ticker_repo = MagicMock()
        fundamental_repo = MagicMock()
        ticker_repo.find_by_ticker.return_value = None

        service = FundamentalService(ticker_repo, fundamental_repo)

        with pytest.raises(GenieError):
            service.get_time_series("999999", None, None)
        fundamental_repo.find_by_ticker.assert_not_called()
