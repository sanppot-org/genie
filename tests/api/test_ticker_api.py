"""Ticker CRUD API 테스트"""

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import app, container
from src.constants import AssetType
from src.database.models import Base, Ticker
from src.database.ticker_repository import TickerRepository
from src.service.ticker_service import TickerService


@pytest.fixture
def test_session() -> Generator[Session, None, None]:
    """테스트용 인메모리 SQLite 세션"""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def repo(test_session: Session) -> TickerRepository:
    """테스트용 TickerRepository"""
    return TickerRepository(test_session)


def test_create_ticker_success(repo: TickerRepository) -> None:
    """새 ticker 생성 성공"""
    # When
    ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)
    saved = repo.save(ticker)

    # Then
    assert saved.id is not None
    assert saved.ticker == "KRW-BTC"
    assert saved.asset_type == AssetType.CRYPTO


def test_create_ticker_duplicate_updates(repo: TickerRepository) -> None:
    """중복 ticker 저장 시 업데이트 (upsert)"""
    # Given: 이미 존재하는 ticker
    ticker1 = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)
    repo.save(ticker1)

    # When: 동일한 ticker로 다시 저장
    ticker2 = Ticker(ticker="KRW-BTC", asset_type=AssetType.ETF)
    saved = repo.save(ticker2)

    # Then: 업데이트됨
    assert repo.find_by_ticker("KRW-BTC").asset_type == AssetType.ETF
    assert len(repo.find_all()) == 1


def test_find_all_tickers(repo: TickerRepository) -> None:
    """전체 ticker 조회"""
    # Given: 여러 ticker 생성
    repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO))
    repo.save(Ticker(ticker="KRW-ETH", asset_type=AssetType.CRYPTO))

    # When
    tickers = repo.find_all()

    # Then
    assert len(tickers) == 2
    assert any(t.ticker == "KRW-BTC" for t in tickers)
    assert any(t.ticker == "KRW-ETH" for t in tickers)


def test_find_ticker_by_id(repo: TickerRepository) -> None:
    """ID로 ticker 조회"""
    # Given: ticker 생성
    saved = repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO))

    # When
    found = repo.find_by_id(saved.id)

    # Then
    assert found is not None
    assert found.ticker == "KRW-BTC"
    assert found.id == saved.id


def test_find_ticker_not_found_returns_none(repo: TickerRepository) -> None:
    """존재하지 않는 ticker 조회 시 None 반환"""
    # When
    found = repo.find_by_id(999)

    # Then
    assert found is None


def test_delete_ticker_success(repo: TickerRepository) -> None:
    """ticker 삭제 성공"""
    # Given: ticker 생성
    saved = repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO))
    ticker_id = saved.id

    # When
    result = repo.delete_by_id(ticker_id)

    # Then
    assert result is True
    assert repo.find_by_id(ticker_id) is None


def test_delete_ticker_not_found_returns_false(repo: TickerRepository) -> None:
    """존재하지 않는 ticker 삭제 시 False 반환"""
    # When
    result = repo.delete_by_id(999)

    # Then
    assert result is False


def test_exists_returns_true_when_exists(repo: TickerRepository) -> None:
    """ticker가 존재하면 True 반환"""
    # Given
    repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO))

    # When/Then
    assert repo.exists("KRW-BTC") is True


def test_exists_returns_false_when_not_exists(repo: TickerRepository) -> None:
    """ticker가 존재하지 않으면 False 반환"""
    assert repo.exists("KRW-BTC") is False


# ============================================================================
# API 엔드포인트 테스트
# ============================================================================


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
    """POST /api/tickers 테스트"""

    def test_생성_성공(
            self,
            client_with_mock: TestClient,
            mock_ticker_service: MagicMock,
    ) -> None:
        """새 ticker 생성 시 201 응답을 반환한다"""
        # Given
        mock_ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)
        mock_ticker.id = 1
        mock_ticker_service.upsert.return_value = mock_ticker

        # When
        response = client_with_mock.post(
            "/api/tickers",
            json={"ticker": "KRW-BTC", "asset_type": "CRYPTO"},
        )

        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["data"]["id"] == 1
        assert data["data"]["ticker"] == "KRW-BTC"
        assert data["data"]["asset_type"] == "CRYPTO"
        mock_ticker_service.upsert.assert_called_once_with(
            ticker="KRW-BTC", asset_type=AssetType.CRYPTO
        )

    def test_잘못된_asset_type_실패(self) -> None:
        """유효하지 않은 asset_type으로 요청하면 422 에러를 반환한다"""
        # Given
        client = TestClient(app)

        # When
        response = client.post(
            "/api/tickers",
            json={"ticker": "KRW-BTC", "asset_type": "INVALID"},
        )

        # Then
        assert response.status_code == 422

    def test_ticker_누락_실패(self) -> None:
        """ticker가 누락되면 422 에러를 반환한다"""
        # Given
        client = TestClient(app)

        # When
        response = client.post(
            "/api/tickers",
            json={"asset_type": "CRYPTO"},
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
        ticker1 = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)
        ticker1.id = 1
        ticker2 = Ticker(ticker="KRW-ETH", asset_type=AssetType.CRYPTO)
        ticker2.id = 2
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
        mock_ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)
        mock_ticker.id = 1
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
