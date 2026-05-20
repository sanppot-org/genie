"""GET /api/dividends API 테스트."""

from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app import app, container
from src.database.models import StockDividend, Ticker
from src.service.dividend_service import DividendService
from src.service.exceptions import GenieError


@pytest.fixture
def mock_dividend_service() -> MagicMock:
    return MagicMock(spec=DividendService)


@pytest.fixture
def client(mock_dividend_service: MagicMock) -> Generator[TestClient, None, None]:
    container.dividend_service.override(mock_dividend_service)
    yield TestClient(app, raise_server_exceptions=False)
    container.dividend_service.reset_override()


class TestGetDividendsAPI:
    def test_정상_이력_반환(
            self, client: TestClient, mock_dividend_service: MagicMock,
    ) -> None:
        ticker = MagicMock(spec=Ticker, ticker="005930")
        ticker.name = "삼성전자"
        row = MagicMock(
            spec=StockDividend,
            record_date=date(2024, 12, 27), kind="SETTLE",
            dps=361.0, fiscal_year=2024,
        )
        mock_dividend_service.get_history.return_value = (ticker, [row])

        response = client.get("/api/dividends?ticker=005930&from=20240101&to=20241231")

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["ticker"] == "005930"
        assert body["name"] == "삼성전자"
        assert len(body["points"]) == 1
        assert body["points"][0]["record_date"] == "2024-12-27"
        assert body["points"][0]["kind"] == "SETTLE"
        assert body["points"][0]["dps"] == 361.0
        assert body["points"][0]["fiscal_year"] == 2024
        mock_dividend_service.get_history.assert_called_once_with(
            "005930", date(2024, 1, 1), date(2024, 12, 31),
        )

    def test_미발견_ticker_404(
            self, client: TestClient, mock_dividend_service: MagicMock,
    ) -> None:
        mock_dividend_service.get_history.side_effect = GenieError.not_found(0)

        response = client.get("/api/dividends?ticker=999999")

        assert response.status_code == 404

    def test_잘못된_from_format_422(self, client: TestClient) -> None:
        response = client.get("/api/dividends?ticker=005930&from=2024-01-01")
        assert response.status_code == 422
