"""Tests for DI Container."""

import os

import pytest

from src.container import ApplicationContainer


@pytest.fixture(autouse=True)
def set_test_env() -> None:
    """테스트용 환경 변수 설정"""
    os.environ["POSTGRES_PASSWORD"] = "test_password"


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
    price_repo = container.price_repository()

    # Then
    assert minute1_repo is not None
    assert daily_repo is not None
    assert price_repo is not None
    assert minute1_repo.session is not None
    assert daily_repo.session is not None
    assert price_repo.session is not None


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
