"""Tests for BaseRepository."""

from datetime import UTC, datetime

import pytest

from src.database.base_repository import BaseRepository
from src.database.models import CandleMinute1


class CandleMinute1RepositoryImpl(BaseRepository[CandleMinute1, int]):
    """Concrete implementation for testing."""

    def _get_model_class(self) -> type[CandleMinute1]:
        return CandleMinute1

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("timestamp", "ticker")


@pytest.fixture
def candle_repo_impl(session):
    """Fixture for concrete repository implementation."""
    return CandleMinute1RepositoryImpl(session)


def test_save_creates_new_entity(candle_repo_impl):
    """save 메서드로 새 엔티티 생성"""
    # Given
    candle = CandleMinute1(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        localtime=datetime(2024, 1, 1, 18, 0, 0),
        ticker="KRW-BTC",
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
    assert all_candles[0].ticker == "KRW-BTC"
    assert all_candles[0].close == 50500000.0


def test_find_all_returns_all_entities(candle_repo_impl):
    """find_all로 모든 엔티티 조회"""
    # Given
    candle1 = CandleMinute1(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        localtime=datetime(2024, 1, 1, 18, 0, 0),
        ticker="KRW-BTC",
        open=50000000.0,
        high=51000000.0,
        low=49000000.0,
        close=50500000.0,
        volume=100.0,
    )
    candle2 = CandleMinute1(
        timestamp=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        localtime=datetime(2024, 1, 1, 19, 0, 0),
        ticker="KRW-ETH",
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
