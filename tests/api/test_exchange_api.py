"""Exchange CRUD API 테스트"""

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import app, container
from src.api.schemas import ExchangeCreate
from src.database.exchange_repository import ExchangeRepository
from src.database.models import Base, Exchange
from src.service.exchange_service import ExchangeService


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
def exchange_repo(test_session: Session) -> ExchangeRepository:
    """테스트용 ExchangeRepository"""
    return ExchangeRepository(test_session)


# ============================================================================
# Repository 레벨 테스트
# ============================================================================


def test_create_exchange_success(exchange_repo: ExchangeRepository) -> None:
    """새 exchange 생성 성공"""
    # When
    exchange = Exchange(name="Upbit", timezone="Asia/Seoul")
    saved = exchange_repo.save(exchange)

    # Then
    assert saved.id is not None
    assert saved.name == "Upbit"
    assert saved.timezone == "Asia/Seoul"


def test_create_exchange_duplicate_updates(exchange_repo: ExchangeRepository) -> None:
    """중복 exchange 저장 시 업데이트 (upsert)"""
    # Given: 이미 존재하는 exchange
    exchange1 = Exchange(name="Upbit", timezone="Asia/Seoul")
    exchange_repo.save(exchange1)

    # When: 동일한 name으로 다시 저장
    exchange2 = Exchange(name="Upbit", timezone="UTC")
    saved = exchange_repo.save(exchange2)

    # Then: 업데이트됨
    assert exchange_repo.find_by_name("Upbit").timezone == "UTC"
    assert len(exchange_repo.find_all()) == 1


def test_find_all_exchanges(exchange_repo: ExchangeRepository) -> None:
    """전체 exchange 조회"""
    # Given: 여러 exchange 생성
    exchange_repo.save(Exchange(name="Upbit", timezone="Asia/Seoul"))
    exchange_repo.save(Exchange(name="Binance", timezone="UTC"))

    # When
    exchanges = exchange_repo.find_all()

    # Then
    assert len(exchanges) == 2
    assert any(e.name == "Upbit" for e in exchanges)
    assert any(e.name == "Binance" for e in exchanges)


def test_find_exchange_by_id(exchange_repo: ExchangeRepository) -> None:
    """ID로 exchange 조회"""
    # Given: exchange 생성
    saved = exchange_repo.save(Exchange(name="Upbit", timezone="Asia/Seoul"))

    # When
    found = exchange_repo.find_by_id(saved.id)

    # Then
    assert found is not None
    assert found.name == "Upbit"
    assert found.id == saved.id


def test_find_exchange_not_found_returns_none(exchange_repo: ExchangeRepository) -> None:
    """존재하지 않는 exchange 조회 시 None 반환"""
    # When
    found = exchange_repo.find_by_id(999)

    # Then
    assert found is None


def test_delete_exchange_success(exchange_repo: ExchangeRepository) -> None:
    """exchange 삭제 성공"""
    # Given: exchange 생성
    saved = exchange_repo.save(Exchange(name="Upbit", timezone="Asia/Seoul"))
    exchange_id = saved.id

    # When
    result = exchange_repo.delete_by_id(exchange_id)

    # Then
    assert result is True
    assert exchange_repo.find_by_id(exchange_id) is None


def test_delete_exchange_not_found_returns_false(exchange_repo: ExchangeRepository) -> None:
    """존재하지 않는 exchange 삭제 시 False 반환"""
    # When
    result = exchange_repo.delete_by_id(999)

    # Then
    assert result is False


# ============================================================================
# API 엔드포인트 테스트
# ============================================================================


def _create_mock_exchange(
        exchange_id: int,
        name: str,
        timezone: str,
) -> MagicMock:
    """Mock Exchange 생성 헬퍼"""
    mock_exchange = MagicMock(spec=Exchange)
    mock_exchange.id = exchange_id
    mock_exchange.name = name
    mock_exchange.timezone = timezone
    return mock_exchange


@pytest.fixture
def mock_exchange_service() -> MagicMock:
    """Mock ExchangeService 픽스처"""
    return MagicMock(spec=ExchangeService)


@pytest.fixture
def client_with_mock(mock_exchange_service: MagicMock) -> Generator[TestClient, None, None]:
    """DI override가 적용된 TestClient 픽스처"""
    container.exchange_service.override(mock_exchange_service)
    yield TestClient(app)
    container.exchange_service.reset_override()


class TestCreateExchangeAPI:
    """POST /api/exchanges 테스트"""

    def test_생성_성공(
            self,
            client_with_mock: TestClient,
            mock_exchange_service: MagicMock,
    ) -> None:
        """새 exchange 생성 시 201 응답을 반환한다"""
        # Given
        mock_exchange = _create_mock_exchange(
            exchange_id=1,
            name="Upbit",
            timezone="Asia/Seoul",
        )
        mock_exchange_service.create.return_value = mock_exchange

        # When
        response = client_with_mock.post(
            "/api/exchanges",
            json={"name": "Upbit", "timezone": "Asia/Seoul"},
        )

        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "Upbit"
        assert data["data"]["timezone"] == "Asia/Seoul"
        mock_exchange_service.create.assert_called_once_with(
            ExchangeCreate(name="Upbit", timezone="Asia/Seoul")
        )

    def test_name_누락_실패(self) -> None:
        """name이 누락되면 422 에러를 반환한다"""
        # Given
        client = TestClient(app)

        # When
        response = client.post(
            "/api/exchanges",
            json={"timezone": "Asia/Seoul"},
        )

        # Then
        assert response.status_code == 422

    def test_timezone_누락_실패(self) -> None:
        """timezone이 누락되면 422 에러를 반환한다"""
        # Given
        client = TestClient(app)

        # When
        response = client.post(
            "/api/exchanges",
            json={"name": "Upbit"},
        )

        # Then
        assert response.status_code == 422

    def test_이미_존재하는_name_실패(
            self,
            mock_exchange_service: MagicMock,
    ) -> None:
        """이미 존재하는 name으로 생성 시 409 에러를 반환한다"""
        # Given
        from src.service.exceptions import GenieError

        mock_exchange_service.create.side_effect = GenieError.already_exists("Upbit")
        container.exchange_service.override(mock_exchange_service)
        client = TestClient(app, raise_server_exceptions=False)

        # When
        response = client.post(
            "/api/exchanges",
            json={"name": "Upbit", "timezone": "Asia/Seoul"},
        )

        # Then
        assert response.status_code == 409
        container.exchange_service.reset_override()


class TestUpdateExchangeAPI:
    """PUT /api/exchanges/{exchange_id} 테스트"""

    def test_수정_성공(
            self,
            client_with_mock: TestClient,
            mock_exchange_service: MagicMock,
    ) -> None:
        """exchange 수정 시 200 응답을 반환한다"""
        # Given
        mock_exchange = _create_mock_exchange(
            exchange_id=1,
            name="Upbit",
            timezone="UTC",
        )
        mock_exchange_service.update.return_value = mock_exchange

        # When
        response = client_with_mock.put(
            "/api/exchanges/1",
            json={"timezone": "UTC"},
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["timezone"] == "UTC"

    def test_존재하지_않는_ID_수정_실패(
            self,
            mock_exchange_service: MagicMock,
    ) -> None:
        """존재하지 않는 ID로 수정 시 404 에러를 반환한다"""
        # Given
        from src.service.exceptions import GenieError

        mock_exchange_service.update.side_effect = GenieError.not_found(999)
        container.exchange_service.override(mock_exchange_service)
        client = TestClient(app, raise_server_exceptions=False)

        # When
        response = client.put(
            "/api/exchanges/999",
            json={"name": "NewName"},
        )

        # Then
        assert response.status_code == 404
        container.exchange_service.reset_override()


class TestGetAllExchangesAPI:
    """GET /api/exchanges 테스트"""

    def test_전체_조회_성공(
            self,
            client_with_mock: TestClient,
            mock_exchange_service: MagicMock,
    ) -> None:
        """전체 exchange 조회 시 200 응답을 반환한다"""
        # Given
        exchange1 = _create_mock_exchange(1, "Upbit", "Asia/Seoul")
        exchange2 = _create_mock_exchange(2, "Binance", "UTC")
        mock_exchange_service.get_all.return_value = [exchange1, exchange2]

        # When
        response = client_with_mock.get("/api/exchanges")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "Upbit"
        assert data["data"][1]["name"] == "Binance"

    def test_빈_목록_조회_성공(
            self,
            client_with_mock: TestClient,
            mock_exchange_service: MagicMock,
    ) -> None:
        """exchange가 없을 때 빈 배열을 반환한다"""
        # Given
        mock_exchange_service.get_all.return_value = []

        # When
        response = client_with_mock.get("/api/exchanges")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []


class TestGetExchangeByIdAPI:
    """GET /api/exchanges/{exchange_id} 테스트"""

    def test_ID로_조회_성공(
            self,
            client_with_mock: TestClient,
            mock_exchange_service: MagicMock,
    ) -> None:
        """ID로 exchange 조회 시 200 응답을 반환한다"""
        # Given
        mock_exchange = _create_mock_exchange(1, "Upbit", "Asia/Seoul")
        mock_exchange_service.get_by_id.return_value = mock_exchange

        # When
        response = client_with_mock.get("/api/exchanges/1")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "Upbit"
        mock_exchange_service.get_by_id.assert_called_once_with(1)

    def test_존재하지_않는_ID_조회_실패(
            self,
            mock_exchange_service: MagicMock,
    ) -> None:
        """존재하지 않는 ID로 조회 시 404 에러를 반환한다"""
        # Given
        from src.service.exceptions import GenieError

        mock_exchange_service.get_by_id.side_effect = GenieError.not_found(999)
        container.exchange_service.override(mock_exchange_service)
        client = TestClient(app, raise_server_exceptions=False)

        # When
        response = client.get("/api/exchanges/999")

        # Then
        assert response.status_code == 404
        container.exchange_service.reset_override()


class TestDeleteExchangeAPI:
    """DELETE /api/exchanges/{exchange_id} 테스트"""

    def test_삭제_성공(
            self,
            client_with_mock: TestClient,
            mock_exchange_service: MagicMock,
    ) -> None:
        """exchange 삭제 시 204 응답을 반환한다"""
        # Given
        mock_exchange_service.delete.return_value = None

        # When
        response = client_with_mock.delete("/api/exchanges/1")

        # Then
        assert response.status_code == 204
        mock_exchange_service.delete.assert_called_once_with(1)
