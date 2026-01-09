"""ExchangeRepository 테스트"""

import pytest
from sqlalchemy.orm import Session

from src.database.exchange_repository import ExchangeRepository
from src.database.models import Exchange


class TestExchangeRepository:
    """ExchangeRepository 테스트"""

    @pytest.fixture
    def exchange_repo(self, session: Session) -> ExchangeRepository:
        """ExchangeRepository fixture"""
        return ExchangeRepository(session)

    def test_save_creates_new_exchange(self, exchange_repo: ExchangeRepository) -> None:
        """새로운 거래소 저장 테스트"""
        exchange = Exchange(name="Upbit")

        result = exchange_repo.save(exchange)

        assert result.id is not None
        assert result.name == "Upbit"

    def test_save_updates_existing_exchange(self, exchange_repo: ExchangeRepository) -> None:
        """기존 거래소 업데이트 테스트 (upsert)"""
        exchange1 = Exchange(name="Upbit")
        saved = exchange_repo.save(exchange1)
        original_id = saved.id

        # 같은 이름으로 다시 저장하면 업데이트되어야 함
        exchange2 = Exchange(name="Upbit")
        result = exchange_repo.save(exchange2)

        assert result.id == original_id

    def test_find_by_name_returns_exchange_when_exists(self, exchange_repo: ExchangeRepository) -> None:
        """이름으로 거래소 조회 테스트 - 존재하는 경우"""
        exchange = Exchange(name="Binance")
        exchange_repo.save(exchange)

        result = exchange_repo.find_by_name("Binance")

        assert result is not None
        assert result.name == "Binance"

    def test_find_by_name_returns_none_when_not_exists(self, exchange_repo: ExchangeRepository) -> None:
        """이름으로 거래소 조회 테스트 - 존재하지 않는 경우"""
        result = exchange_repo.find_by_name("NonExistent")

        assert result is None

    def test_exists_returns_true_when_exists(self, exchange_repo: ExchangeRepository) -> None:
        """거래소 존재 여부 테스트 - 존재하는 경우"""
        exchange = Exchange(name="Coinbase")
        exchange_repo.save(exchange)

        result = exchange_repo.exists("Coinbase")

        assert result is True

    def test_exists_returns_false_when_not_exists(self, exchange_repo: ExchangeRepository) -> None:
        """거래소 존재 여부 테스트 - 존재하지 않는 경우"""
        result = exchange_repo.exists("NonExistent")

        assert result is False

    def test_delete_by_id_removes_exchange(self, exchange_repo: ExchangeRepository) -> None:
        """ID로 거래소 삭제 테스트"""
        exchange = Exchange(name="Kraken")
        saved = exchange_repo.save(exchange)

        result = exchange_repo.delete_by_id(saved.id)

        assert result is True
        assert exchange_repo.find_by_name("Kraken") is None

    def test_find_all_returns_all_exchanges(self, exchange_repo: ExchangeRepository) -> None:
        """모든 거래소 조회 테스트"""
        exchange_repo.save(Exchange(name="Exchange1"))
        exchange_repo.save(Exchange(name="Exchange2"))
        exchange_repo.save(Exchange(name="Exchange3"))

        result = exchange_repo.find_all()

        assert len(result) == 3
