"""Pytest fixtures shared across all test modules."""

from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.candle_repositories import CandleDailyRepository, CandleMinute1Repository
from src.database.database import Database
from src.database.models import Base, Ticker
from src.database.ticker_repository import TickerRepository


@pytest.fixture
def db() -> Generator[Database, Any, None]:
    """테스트용 데이터베이스 (SQLite 인메모리)"""
    engine = create_engine("sqlite:///:memory:", echo=False)

    database = Database.__new__(Database)
    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    yield database

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def session(db: Database) -> Generator[Session, Any, None]:
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
def ticker_repo(session: Session) -> TickerRepository:
    """Ticker Repository fixture"""
    return TickerRepository(session)


@pytest.fixture
def sample_ticker(ticker_repo: TickerRepository) -> Ticker:
    """테스트용 Ticker 엔티티 생성 fixture"""
    ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value)
    ticker_repo.save(ticker)
    return ticker
