"""Pytest fixtures for service tests."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.adapters.adapter_factory import CandleAdapterFactory
from src.database.candle_repositories import CandleDailyRepository, CandleMinute1Repository
from src.database.database import Database
from src.service.candle_service import CandleService


@pytest.fixture
def db() -> Database:
    """테스트용 데이터베이스 (SQLite 인메모리)"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.database.models import Base

    engine = create_engine("sqlite:///:memory:", echo=False)
    database = Database.__new__(Database)
    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    yield database

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def session(db: Database) -> Session:
    """테스트용 세션"""
    session = db.get_session()
    yield session
    session.close()


@pytest.fixture
def minute1_repo(session: Session) -> CandleMinute1Repository:
    """1분봉 캔들 Repository fixture"""
    return CandleMinute1Repository(session)


@pytest.fixture
def daily_repo(session: Session) -> CandleDailyRepository:
    """일봉 캔들 Repository fixture"""
    return CandleDailyRepository(session)


@pytest.fixture
def adapter_factory() -> CandleAdapterFactory:
    """어댑터 팩토리 fixture"""
    return CandleAdapterFactory()


@pytest.fixture
def candle_service(
        minute1_repo: CandleMinute1Repository,
        daily_repo: CandleDailyRepository,
        adapter_factory: CandleAdapterFactory,
) -> CandleService:
    """CandleService fixture"""
    return CandleService(minute1_repo, daily_repo, adapter_factory)


@pytest.fixture
def mock_upbit_api() -> MagicMock:
    """Mock UpbitAPI fixture"""
    return MagicMock()
