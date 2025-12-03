"""Tests for BaseRepository."""

from datetime import UTC, datetime

import pytest

from src.database.base_repository import BaseRepository
from src.database.models import PriceData


class PriceRepositoryImpl(BaseRepository[PriceData, int]):
    """Concrete implementation for testing."""

    def _get_model_class(self) -> type[PriceData]:
        return PriceData

    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        return ("timestamp", "symbol", "source")


@pytest.fixture
def price_repo_impl(session):
    """Fixture for concrete repository implementation."""
    return PriceRepositoryImpl(session)


def test_save_creates_new_entity(price_repo_impl):
    """save 메서드로 새 엔티티 생성"""
    # Given
    price = PriceData(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        symbol="USD-KRW",
        price=1300.0,
        source="yfinance",
    )

    # When
    saved = price_repo_impl.save(price)

    # Then
    assert saved.id is not None
    assert saved.symbol == "USD-KRW"


def test_find_by_id_returns_entity(price_repo_impl):
    """find_by_id로 엔티티 조회"""
    # Given
    price = PriceData(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        symbol="USD-KRW",
        price=1300.0,
        source="yfinance",
    )
    saved = price_repo_impl.save(price)

    # When
    found = price_repo_impl.find_by_id(saved.id)

    # Then
    assert found is not None
    assert found.id == saved.id
    assert found.symbol == "USD-KRW"


def test_find_by_id_returns_none_when_not_found(price_repo_impl):
    """존재하지 않는 ID로 조회시 None 반환"""
    # When
    found = price_repo_impl.find_by_id(99999)

    # Then
    assert found is None


def test_find_all_returns_all_entities(price_repo_impl):
    """find_all로 모든 엔티티 조회"""
    # Given
    price1 = PriceData(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        symbol="USD-KRW",
        price=1300.0,
        source="yfinance",
    )
    price2 = PriceData(
        timestamp=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        symbol="GOLD-KRW",
        price=80000.0,
        source="yfinance",
    )
    price_repo_impl.save(price1)
    price_repo_impl.save(price2)

    # When
    all_prices = price_repo_impl.find_all()

    # Then
    assert len(all_prices) == 2


def test_delete_by_id_deletes_entity(price_repo_impl):
    """delete_by_id로 엔티티 삭제"""
    # Given
    price = PriceData(
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        symbol="USD-KRW",
        price=1300.0,
        source="yfinance",
    )
    saved = price_repo_impl.save(price)

    # When
    result = price_repo_impl.delete_by_id(saved.id)

    # Then
    assert result is True
    assert price_repo_impl.find_by_id(saved.id) is None


def test_delete_by_id_returns_false_when_not_found(price_repo_impl):
    """존재하지 않는 ID 삭제시 False 반환"""
    # When
    result = price_repo_impl.delete_by_id(99999)

    # Then
    assert result is False
