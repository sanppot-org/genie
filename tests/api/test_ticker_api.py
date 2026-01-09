"""Ticker CRUD API 테스트"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Ticker
from src.database.ticker_repository import TickerRepository


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
    ticker = Ticker(ticker="KRW-BTC", asset_type="CRYPTO")
    saved = repo.save(ticker)

    # Then
    assert saved.id is not None
    assert saved.ticker == "KRW-BTC"
    assert saved.asset_type == "CRYPTO"


def test_create_ticker_duplicate_updates(repo: TickerRepository) -> None:
    """중복 ticker 저장 시 업데이트 (upsert)"""
    # Given: 이미 존재하는 ticker
    ticker1 = Ticker(ticker="KRW-BTC", asset_type="CRYPTO")
    repo.save(ticker1)

    # When: 동일한 ticker로 다시 저장
    ticker2 = Ticker(ticker="KRW-BTC", asset_type="ETF")
    saved = repo.save(ticker2)

    # Then: 업데이트됨
    assert repo.find_by_ticker("KRW-BTC").asset_type == "ETF"
    assert len(repo.find_all()) == 1


def test_find_all_tickers(repo: TickerRepository) -> None:
    """전체 ticker 조회"""
    # Given: 여러 ticker 생성
    repo.save(Ticker(ticker="KRW-BTC", asset_type="CRYPTO"))
    repo.save(Ticker(ticker="KRW-ETH", asset_type="CRYPTO"))

    # When
    tickers = repo.find_all()

    # Then
    assert len(tickers) == 2
    assert any(t.ticker == "KRW-BTC" for t in tickers)
    assert any(t.ticker == "KRW-ETH" for t in tickers)


def test_find_ticker_by_id(repo: TickerRepository) -> None:
    """ID로 ticker 조회"""
    # Given: ticker 생성
    saved = repo.save(Ticker(ticker="KRW-BTC", asset_type="CRYPTO"))

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
    saved = repo.save(Ticker(ticker="KRW-BTC", asset_type="CRYPTO"))
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
    repo.save(Ticker(ticker="KRW-BTC", asset_type="CRYPTO"))

    # When/Then
    assert repo.exists("KRW-BTC") is True


def test_exists_returns_false_when_not_exists(repo: TickerRepository) -> None:
    """ticker가 존재하지 않으면 False 반환"""
    assert repo.exists("KRW-BTC") is False
