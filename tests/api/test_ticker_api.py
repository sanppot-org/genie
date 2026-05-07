"""Ticker CRUD API 테스트"""

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app import app, container
from src.api.schemas import TickerCreate
from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker
from src.service.ticker_service import TickerService


def _create_mock_ticker(
        ticker_id: int,
        ticker_code: str,
        asset_type: AssetType,
        data_source: str = DataSource.UPBIT.value,
) -> MagicMock:
    """Mock Ticker 생성 헬퍼"""
    mock_ticker = MagicMock(spec=Ticker)
    mock_ticker.id = ticker_id
    mock_ticker.ticker = ticker_code
    mock_ticker.asset_type = asset_type
    mock_ticker.data_source = data_source

    return mock_ticker


@pytest.fixture
def mock_ticker_service() -> MagicMock:
    """Mock TickerService 픽스처"""
    return MagicMock(spec=TickerService)


@pytest.fixture
def client_with_mock(mock_ticker_service: MagicMock) -> Generator[TestClient, None, None]:
    """DI override가 적용된 TestClient 픽스처"""
    container.ticker_service.override(mock_ticker_service)
    yield TestClient(app)
    container.ticker_service.reset_override()


class TestCreateTickerAPI:
    """PUT /api/tickers 테스트"""

    def test_생성_성공(
            self,
            client_with_mock: TestClient,
            mock_ticker_service: MagicMock,
    ) -> None:
        """새 ticker 생성 시 201 응답을 반환한다"""
        # Given
        mock_ticker = _create_mock_ticker(
            ticker_id=1,
            ticker_code="KRW-BTC",
            asset_type=AssetType.CRYPTO,
            data_source=DataSource.UPBIT.value,
        )
        mock_ticker_service.upsert.return_value = mock_ticker

        # When
        response = client_with_mock.put(
            "/api/tickers",
            json={"ticker": "KRW-BTC", "asset_type": "CRYPTO", "data_source": "upbit"},
        )

        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["data"]["id"] == 1
        assert data["data"]["ticker"] == "KRW-BTC"
        assert data["data"]["asset_type"] == "CRYPTO"
        assert data["data"]["data_source"] == "upbit"
        assert data["data"]["timezone"] == "Asia/Seoul"
        mock_ticker_service.upsert.assert_called_once_with(
            TickerCreate(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT)
        )

    def test_잘못된_asset_type_실패(self) -> None:
        """유효하지 않은 asset_type으로 요청하면 422 에러를 반환한다"""
        # Given
        client = TestClient(app)

        # When
        response = client.put(
            "/api/tickers",
            json={"ticker": "KRW-BTC", "asset_type": "INVALID", "data_source": "upbit"},
        )

        # Then
        assert response.status_code == 422

    def test_ticker_누락_실패(self) -> None:
        """ticker가 누락되면 422 에러를 반환한다"""
        # Given
        client = TestClient(app)

        # When
        response = client.put(
            "/api/tickers",
            json={"asset_type": "CRYPTO", "data_source": "upbit"},
        )

        # Then
        assert response.status_code == 422

    def test_data_source_누락_실패(self) -> None:
        """data_source가 누락되면 422 에러를 반환한다"""
        # Given
        client = TestClient(app)

        # When
        response = client.put(
            "/api/tickers",
            json={"ticker": "KRW-BTC", "asset_type": "CRYPTO"},
        )

        # Then
        assert response.status_code == 422


class TestGetAllTickersAPI:
    """GET /api/tickers 테스트"""

    def test_전체_조회_성공(
            self,
            client_with_mock: TestClient,
            mock_ticker_service: MagicMock,
    ) -> None:
        """전체 ticker 조회 시 200 응답을 반환한다"""
        # Given
        ticker1 = _create_mock_ticker(1, "KRW-BTC", AssetType.CRYPTO)
        ticker2 = _create_mock_ticker(2, "KRW-ETH", AssetType.CRYPTO)
        mock_ticker_service.get_all.return_value = [ticker1, ticker2]

        # When
        response = client_with_mock.get("/api/tickers")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["data"][0]["ticker"] == "KRW-BTC"
        assert data["data"][1]["ticker"] == "KRW-ETH"

    def test_빈_목록_조회_성공(
            self,
            client_with_mock: TestClient,
            mock_ticker_service: MagicMock,
    ) -> None:
        """ticker가 없을 때 빈 배열을 반환한다"""
        # Given
        mock_ticker_service.get_all.return_value = []

        # When
        response = client_with_mock.get("/api/tickers")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []


class TestGetTickerByIdAPI:
    """GET /api/tickers/{ticker_id} 테스트"""

    def test_ID로_조회_성공(
            self,
            client_with_mock: TestClient,
            mock_ticker_service: MagicMock,
    ) -> None:
        """ID로 ticker 조회 시 200 응답을 반환한다"""
        # Given
        mock_ticker = _create_mock_ticker(1, "KRW-BTC", AssetType.CRYPTO)
        mock_ticker_service.get_by_id.return_value = mock_ticker

        # When
        response = client_with_mock.get("/api/tickers/1")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == 1
        assert data["data"]["ticker"] == "KRW-BTC"
        mock_ticker_service.get_by_id.assert_called_once_with(1)

    def test_존재하지_않는_ID_조회_실패(
            self,
            mock_ticker_service: MagicMock,
    ) -> None:
        """존재하지 않는 ID로 조회 시 404 에러를 반환한다"""
        # Given
        from src.service.exceptions import GenieError

        mock_ticker_service.get_by_id.side_effect = GenieError.not_found(999)
        container.ticker_service.override(mock_ticker_service)
        client = TestClient(app, raise_server_exceptions=False)

        # When
        response = client.get("/api/tickers/999")

        # Then
        assert response.status_code == 404
        container.ticker_service.reset_override()


class TestDeleteTickerAPI:
    """DELETE /api/tickers/{ticker_id} 테스트"""

    def test_삭제_성공(
            self,
            client_with_mock: TestClient,
            mock_ticker_service: MagicMock,
    ) -> None:
        """ticker 삭제 시 204 응답을 반환한다"""
        # Given
        mock_ticker_service.delete.return_value = None

        # When
        response = client_with_mock.delete("/api/tickers/1")

        # Then
        assert response.status_code == 204
        mock_ticker_service.delete.assert_called_once_with(1)
