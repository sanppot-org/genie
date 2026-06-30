"""Tests for DI Container."""

from collections.abc import Generator

import pytest

from src.container import ApplicationContainer


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트용 환경 변수 설정 (monkeypatch로 테스트 종료 시 자동 복원)."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")


@pytest.fixture(autouse=True)
def _restore_global_wiring() -> Generator[None, None, None]:
    """app 글로벌 컨테이너 와이어링 복원 (테스트 격리).

    ApplicationContainer는 wiring_config.auto_wire=True라 인스턴스화할 때마다
    라우트 모듈(@inject)을 그 인스턴스로 재바인딩한다. 이 파일이 새 인스턴스를
    여러 개 만들면 app.py의 글로벌 컨테이너 바인딩을 가로채, 이후 실행되는 API
    테스트의 `container.x.override()`가 무력화된다(라우트가 실제 서비스→실DB로
    빠져 500/단언 실패). 각 테스트 후 app 글로벌 컨테이너를 다시 wire해 복원한다.
    """
    yield
    from app import container as app_container
    app_container.wire()


def test_container_database_config() -> None:
    """DatabaseConfig 제공 테스트"""
    # Given
    container = ApplicationContainer()

    # When
    config = container.database_config()

    # Then
    assert config is not None
    assert config.postgres_db is not None
    assert config.postgres_user is not None
    assert config.postgres_host is not None
    assert config.postgres_port is not None


def test_container_database() -> None:
    """Database 제공 테스트"""
    # Given
    container = ApplicationContainer()

    # When
    database = container.database()

    # Then
    assert database is not None
    assert database.engine is not None
    assert database.SessionLocal is not None


def test_container_repositories() -> None:
    """Repository 제공 테스트"""
    # Given
    container = ApplicationContainer()

    # When
    minute1_repo = container.candle_minute1_repository()
    daily_repo = container.candle_daily_repository()

    # Then
    assert minute1_repo is not None
    assert daily_repo is not None
    assert minute1_repo.session is not None
    assert daily_repo.session is not None


def test_container_database_singleton() -> None:
    """Database가 Singleton으로 제공되는지 테스트"""
    # Given
    container = ApplicationContainer()

    # When
    database1 = container.database()
    database2 = container.database()

    # Then - 같은 인스턴스
    assert database1 is database2


def test_container_repositories_factory() -> None:
    """Repository가 Factory로 제공되는지 테스트"""
    # Given
    container = ApplicationContainer()

    # When
    minute1_repo1 = container.candle_minute1_repository()
    minute1_repo2 = container.candle_minute1_repository()

    # Then - 다른 인스턴스
    assert minute1_repo1 is not minute1_repo2
