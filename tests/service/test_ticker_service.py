"""TickerService 테스트"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.constants import AssetType
from src.database.models import Base
from src.database.ticker_repository import TickerRepository
from src.service.exceptions import GenieError
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
def service(test_session: Session) -> TickerService:
    """테스트용 TickerService"""
    repo = TickerRepository(test_session)
    return TickerService(repo)


def test_upsert_creates_new_ticker(service: TickerService) -> None:
    """새 ticker 생성"""
    # When
    ticker = service.upsert(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)

    # Then
    assert ticker.id is not None
    assert ticker.ticker == "KRW-BTC"
    assert ticker.asset_type == AssetType.CRYPTO


def test_upsert_updates_existing_ticker(service: TickerService) -> None:
    """기존 ticker 업데이트 (upsert)"""
    # Given
    original = service.upsert(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)

    # When
    updated = service.upsert(ticker="KRW-BTC", asset_type=AssetType.ETF)

    # Then
    assert updated.id == original.id
    assert updated.ticker == "KRW-BTC"
    assert updated.asset_type == AssetType.ETF
    assert len(service.get_all()) == 1


def test_get_all_tickers(service: TickerService) -> None:
    """전체 ticker 조회"""
    # Given
    service.upsert(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)
    service.upsert(ticker="KRW-ETH", asset_type=AssetType.CRYPTO)

    # When
    tickers = service.get_all()

    # Then
    assert len(tickers) == 2
    assert any(t.ticker == "KRW-BTC" for t in tickers)
    assert any(t.ticker == "KRW-ETH" for t in tickers)


def test_get_ticker_by_id(service: TickerService) -> None:
    """ID로 ticker 조회"""
    # Given
    created = service.upsert(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)

    # When
    ticker = service.get_by_id(created.id)

    # Then
    assert ticker.id == created.id
    assert ticker.ticker == "KRW-BTC"


def test_get_ticker_raises_when_not_found(service: TickerService) -> None:
    """존재하지 않는 ticker 조회 시 예외 발생"""
    # When/Then
    with pytest.raises(GenieError):
        service.get_by_id(999)


def test_delete_ticker_success(service: TickerService) -> None:
    """ticker 삭제 성공"""
    # Given
    created = service.upsert(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)

    # When
    service.delete(created.id)

    # Then
    with pytest.raises(GenieError):
        service.get_by_id(created.id)


def test_delete_ticker_ignores_when_not_found(service: TickerService) -> None:
    """존재하지 않는 ticker 삭제 시 무시"""
    # When/Then - 예외 없이 정상 실행
    service.delete(999)
