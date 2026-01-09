"""Tests for Ticker model."""

from src.constants import AssetType
from src.database.models import Ticker


class TestTicker:
    """Ticker 모델 테스트."""

    def test_ticker_creation_with_required_fields(self) -> None:
        """필수 필드로 Ticker 생성."""
        # Given & When
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO.value)

        # Then
        assert ticker.ticker == "KRW-BTC"
        assert ticker.asset_type == "CRYPTO"

    def test_ticker_creation_with_stock_type(self) -> None:
        """주식 타입으로 Ticker 생성."""
        # Given & When
        ticker = Ticker(ticker="005930", asset_type=AssetType.STOCK.value)

        # Then
        assert ticker.ticker == "005930"
        assert ticker.asset_type == "STOCK"

    def test_ticker_creation_with_etf_type(self) -> None:
        """ETF 타입으로 Ticker 생성."""
        # Given & When
        ticker = Ticker(ticker="SPY", asset_type=AssetType.ETF.value)

        # Then
        assert ticker.ticker == "SPY"
        assert ticker.asset_type == "ETF"

    def test_ticker_repr(self) -> None:
        """__repr__ 메서드 테스트."""
        # Given
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO.value)

        # When
        result = repr(ticker)

        # Then
        assert "KRW-BTC" in result
        assert "CRYPTO" in result
