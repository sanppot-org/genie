"""Tests for Ticker model."""

from src.constants import AssetType
from src.database.models import Ticker


class TestTicker:
    """Ticker 모델 테스트."""

    def test_ticker_creation_with_required_fields(self) -> None:
        """필수 필드로 Ticker 생성."""
        # Given & When
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, exchange_id=1)

        # Then
        assert ticker.ticker == "KRW-BTC"
        assert ticker.asset_type == AssetType.CRYPTO
        assert ticker.exchange_id == 1

    def test_ticker_creation_with_stock_type(self) -> None:
        """한국 주식 타입으로 Ticker 생성."""
        # Given & When
        ticker = Ticker(ticker="005930", asset_type=AssetType.KR_STOCK, exchange_id=1)

        # Then
        assert ticker.ticker == "005930"
        assert ticker.asset_type == AssetType.KR_STOCK

    def test_ticker_creation_with_etf_type(self) -> None:
        """미국 ETF 타입으로 Ticker 생성."""
        # Given & When
        ticker = Ticker(ticker="SPY", asset_type=AssetType.US_ETF, exchange_id=1)

        # Then
        assert ticker.ticker == "SPY"
        assert ticker.asset_type == AssetType.US_ETF

    def test_ticker_repr(self) -> None:
        """__repr__ 메서드 테스트."""
        # Given
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, exchange_id=1)

        # When
        result = repr(ticker)

        # Then
        assert "KRW-BTC" in result
        assert "CRYPTO" in result
