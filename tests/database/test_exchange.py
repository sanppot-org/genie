"""Exchange 모델 테스트"""

from src.database.models import Exchange


class TestExchange:
    """Exchange 모델 테스트"""

    def test_exchange_creation_with_required_fields(self) -> None:
        """필수 필드로 Exchange 생성 테스트"""
        exchange = Exchange(name="Upbit")

        assert exchange.name == "Upbit"

    def test_exchange_repr(self) -> None:
        """Exchange __repr__ 테스트"""
        exchange = Exchange(id=1, name="Binance")

        result = repr(exchange)

        assert "Exchange" in result
        assert "Binance" in result
