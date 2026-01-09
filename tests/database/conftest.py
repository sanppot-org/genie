"""Pytest fixtures for database tests."""

import pytest
from sqlalchemy.orm import Session

from src.config import DatabaseConfig
from src.database.candle_repositories import CandleDailyRepository, CandleMinute1Repository
from src.database.database import Database
from src.database.exchange_repository import ExchangeRepository


@pytest.fixture
def db_config() -> DatabaseConfig:
    """테스트용 인메모리 데이터베이스 설정"""
    # 인메모리 SQLite 사용 (빠른 테스트)
    return DatabaseConfig(
        postgres_db="test_db",
        postgres_user="test",
        postgres_password="test",  # 테스트에서는 실제로 사용 안 됨
        postgres_host="localhost",
        postgres_port=5432,
    )


@pytest.fixture
def db() -> Database:
    """테스트용 데이터베이스 (SQLite 인메모리)"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.database.database import Database
    from src.database.models import Base

    # SQLite 인메모리 엔진 생성
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Database 객체 생성 (config 없이 직접 설정)
    database = Database.__new__(Database)
    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 테이블 생성
    Base.metadata.create_all(bind=engine)

    yield database

    # 정리
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
def exchange_repo(session: Session) -> ExchangeRepository:
    """거래소 Repository fixture"""
    return ExchangeRepository(session)
