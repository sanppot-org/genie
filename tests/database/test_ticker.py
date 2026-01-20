"""Tests for Ticker model."""

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker


class TestTicker:
    """Ticker 모델 테스트."""

    def test_ticker_creation_with_required_fields(self) -> None:
        """필수 필드로 Ticker 생성."""
        # Given & When
        ticker = Ticker(
            ticker="KRW-BTC",
            asset_type=AssetType.CRYPTO,
            data_source=DataSource.UPBIT.value,
        )

        # Then
        assert ticker.ticker == "KRW-BTC"
        assert ticker.asset_type == AssetType.CRYPTO
        assert ticker.data_source == DataSource.UPBIT.value

    def test_ticker_creation_with_stock_type(self) -> None:
        """한국 주식 타입으로 Ticker 생성."""
        # Given & When
        ticker = Ticker(
            ticker="005930",
            asset_type=AssetType.KR_STOCK,
            data_source=DataSource.HANTU_D.value,
        )

        # Then
        assert ticker.ticker == "005930"
        assert ticker.asset_type == AssetType.KR_STOCK
        assert ticker.data_source == DataSource.HANTU_D.value

    def test_ticker_creation_with_etf_type(self) -> None:
        """미국 ETF 타입으로 Ticker 생성."""
        # Given & When
        ticker = Ticker(
            ticker="SPY",
            asset_type=AssetType.US_ETF,
            data_source=DataSource.HANTU_O.value,
        )

        # Then
        assert ticker.ticker == "SPY"
        assert ticker.asset_type == AssetType.US_ETF
        assert ticker.data_source == DataSource.HANTU_O.value

    def test_ticker_repr(self) -> None:
        """__repr__ 메서드 테스트."""
        # Given
        ticker = Ticker(
            ticker="KRW-BTC",
            asset_type=AssetType.CRYPTO,
            data_source=DataSource.UPBIT.value,
        )

        # When
        result = repr(ticker)

        # Then
        assert "KRW-BTC" in result
        assert "CRYPTO" in result
        assert "upbit" in result
