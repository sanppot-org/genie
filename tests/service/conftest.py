"""Pytest fixtures for service tests."""
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.adapters.adapter_factory import CandleAdapterFactory
from src.constants import AssetType
from src.database.candle_repositories import CandleDailyRepository, CandleMinute1Repository
from src.database.database import Database
from src.database.exchange_repository import ExchangeRepository
from src.database.models import Exchange, Ticker
from src.database.ticker_repository import TickerRepository
from src.service.candle_service import CandleService


@pytest.fixture
def db() -> Generator[Database, Any, None]:
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


@pytest.fixture
def ticker_repo(session: Session) -> TickerRepository:
    """Ticker Repository fixture"""
    return TickerRepository(session)


@pytest.fixture
def exchange_repo(session: Session) -> ExchangeRepository:
    """Exchange Repository fixture"""
    return ExchangeRepository(session)


@pytest.fixture
def sample_exchange(exchange_repo: ExchangeRepository) -> Exchange:
    """테스트용 Exchange 엔티티 생성 fixture

    Returns:
        Exchange: id가 할당된 Exchange 엔티티 (Upbit, Asia/Seoul)
    """
    exchange = Exchange(name="Upbit", timezone="Asia/Seoul")
    exchange_repo.save(exchange)
    return exchange


@pytest.fixture
def sample_ticker(ticker_repo: TickerRepository, sample_exchange: Exchange) -> Ticker:
    """테스트용 Ticker 엔티티 생성 fixture

    Returns:
        Ticker: id가 할당된 Ticker 엔티티
    """
    ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, exchange_id=sample_exchange.id)
    ticker_repo.save(ticker)
    return ticker
