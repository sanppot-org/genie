"""GET /api/fundamentals API 테스트."""

from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app import app, container
from src.database.models import StockFundamental, Ticker
from src.service.exceptions import GenieError
from src.service.fundamental_service import FundamentalService


@pytest.fixture
def mock_fundamental_service() -> MagicMock:
    return MagicMock(spec=FundamentalService)


@pytest.fixture
def client(mock_fundamental_service: MagicMock) -> Generator[TestClient, None, None]:
    container.fundamental_service.override(mock_fundamental_service)
    yield TestClient(app, raise_server_exceptions=False)
    container.fundamental_service.reset_override()


class TestGetFundamentalsAPI:
    def test_정상_시계열_반환(
            self, client: TestClient, mock_fundamental_service: MagicMock,
    ) -> None:
        """ticker 정상 조회 → 200 + ticker/name/points."""
        ticker = MagicMock(spec=Ticker, ticker="005930")
        ticker.name = "삼성전자"  # MagicMock의 name kwarg는 reserved → 명시적 set
        row = MagicMock(
            spec=StockFundamental,
            date=date(2024, 1, 2), per=12.5, pbr=1.4, bps=50000.0,
            eps=4000.0, div=2.5, dps=1250.0,
        )
        mock_fundamental_service.get_time_series.return_value = (ticker, [row])

        response = client.get("/api/fundamentals?ticker=005930&from=20240101&to=20240131")

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["ticker"] == "005930"
        assert body["name"] == "삼성전자"
        assert len(body["points"]) == 1
        assert body["points"][0]["date"] == "2024-01-02"
        assert body["points"][0]["per"] == 12.5
        mock_fundamental_service.get_time_series.assert_called_once_with(
            "005930", date(2024, 1, 1), date(2024, 1, 31),
        )

    def test_미발견_ticker_404(
            self, client: TestClient, mock_fundamental_service: MagicMock,
    ) -> None:
        """ticker 없으면 404."""
        mock_fundamental_service.get_time_series.side_effect = GenieError.not_found(0)

        response = client.get("/api/fundamentals?ticker=999999")

        assert response.status_code == 404

    def test_잘못된_from_format_422(self, client: TestClient) -> None:
        """from 파라미터 패턴 불일치 시 422."""
        response = client.get("/api/fundamentals?ticker=005930&from=2024-01-01")
        assert response.status_code == 422
