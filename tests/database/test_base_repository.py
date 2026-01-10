"""Tests for BaseRepository."""

from datetime import UTC, datetime

import pytest

from src.constants import AssetType
from src.database.base_repository import BaseRepository
from src.database.models import CandleMinute1, Ticker
from src.database.ticker_repository import TickerRepository


class CandleMinute1RepositoryImpl(BaseRepository[CandleMinute1, int]):
    """Concrete implementation for testing."""

    def _get_model_class(self) -> type[CandleMinute1]:
        return CandleMinute1

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("kst_time", "ticker_id")


@pytest.fixture
def candle_repo_impl(session):
    """Fixture for concrete repository implementation."""
    return CandleMinute1RepositoryImpl(session)


@pytest.fixture
def ticker_repo(session):
    """Ticker Repository fixture."""
    return TickerRepository(session)


@pytest.fixture
def sample_tickers(ticker_repo):
    """테스트용 Ticker 엔티티 생성 fixture."""
    btc = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO)
    eth = Ticker(ticker="KRW-ETH", asset_type=AssetType.CRYPTO)
    ticker_repo.save(btc)
    ticker_repo.save(eth)
    return {"BTC": btc, "ETH": eth}


def test_save_creates_new_entity(candle_repo_impl, sample_tickers):
    """save 메서드로 새 엔티티 생성"""
    # Given
    btc_ticker = sample_tickers["BTC"]
    candle = CandleMinute1(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        kst_time=datetime(2024, 1, 1, 18, 0, 0),
        ticker_id=btc_ticker.id,
        open=50000000.0,
        high=51000000.0,
        low=49000000.0,
        close=50500000.0,
        volume=100.0,
    )

    # When
    saved = candle_repo_impl.save(candle)

    # Then - DB에 저장되었는지 조회로 확인
    all_candles = candle_repo_impl.find_all()
    assert len(all_candles) == 1
    assert all_candles[0].ticker_id == btc_ticker.id
    assert all_candles[0].close == 50500000.0


def test_find_all_returns_all_entities(candle_repo_impl, sample_tickers):
    """find_all로 모든 엔티티 조회"""
    # Given
    btc_ticker = sample_tickers["BTC"]
    eth_ticker = sample_tickers["ETH"]
    candle1 = CandleMinute1(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        kst_time=datetime(2024, 1, 1, 18, 0, 0),
        ticker_id=btc_ticker.id,
        open=50000000.0,
        high=51000000.0,
        low=49000000.0,
        close=50500000.0,
        volume=100.0,
    )
    candle2 = CandleMinute1(
        timestamp=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        kst_time=datetime(2024, 1, 1, 19, 0, 0),
        ticker_id=eth_ticker.id,
        open=3000000.0,
        high=3100000.0,
        low=2900000.0,
        close=3050000.0,
        volume=200.0,
    )
    candle_repo_impl.save(candle1)
    candle_repo_impl.save(candle2)

    # When
    all_candles = candle_repo_impl.find_all()

    # Then
    assert len(all_candles) == 2
