"""Tests for TickerRepository."""

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository


class TestTickerRepository:
    """TickerRepository 테스트."""

    def test_save_creates_new_ticker(
            self, ticker_repo: TickerRepository
    ) -> None:
        """save로 새 Ticker 생성."""
        # Given
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value)

        # When
        saved = ticker_repo.save(ticker)

        # Then
        assert saved.id is not None
        assert saved.ticker == "KRW-BTC"
        assert saved.asset_type == AssetType.CRYPTO
        assert saved.data_source == DataSource.UPBIT.value

    def test_save_updates_existing_ticker(
            self, ticker_repo: TickerRepository
    ) -> None:
        """save로 기존 Ticker 업데이트 (upsert)."""
        # Given
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value)
        ticker_repo.save(ticker)

        updated_ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.KR_STOCK, data_source=DataSource.UPBIT.value)

        # When
        saved = ticker_repo.save(updated_ticker)

        # Then
        assert saved.asset_type == AssetType.KR_STOCK
        assert len(ticker_repo.find_all()) == 1

    def test_find_by_ticker_returns_ticker_when_exists(
            self, ticker_repo: TickerRepository
    ) -> None:
        """find_by_ticker로 존재하는 Ticker 조회."""
        # Given
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value)
        ticker_repo.save(ticker)

        # When
        result = ticker_repo.find_by_ticker("KRW-BTC")

        # Then
        assert result is not None
        assert result.ticker == "KRW-BTC"

    def test_find_by_ticker_returns_none_when_not_exists(
            self, ticker_repo: TickerRepository
    ) -> None:
        """find_by_ticker로 존재하지 않는 Ticker 조회시 None 반환."""
        # When
        result = ticker_repo.find_by_ticker("KRW-BTC")

        # Then
        assert result is None

    def test_find_by_asset_type_returns_filtered_tickers(
            self, ticker_repo: TickerRepository
    ) -> None:
        """find_by_asset_type으로 자산 유형별 필터링."""
        # Given
        ticker_repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value))
        ticker_repo.save(Ticker(ticker="KRW-ETH", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value))
        ticker_repo.save(Ticker(ticker="005930", asset_type=AssetType.KR_STOCK, data_source=DataSource.UPBIT.value))

        # When
        result = ticker_repo.find_by_asset_type(AssetType.CRYPTO)

        # Then
        assert len(result) == 2
        assert all(t.asset_type == AssetType.CRYPTO for t in result)

    def test_find_by_asset_type_returns_empty_list_when_no_match(
            self, ticker_repo: TickerRepository
    ) -> None:
        """find_by_asset_type으로 일치하는 항목이 없으면 빈 리스트 반환."""
        # Given
        ticker_repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value))

        # When
        result = ticker_repo.find_by_asset_type(AssetType.KR_STOCK)

        # Then
        assert result == []

    def test_exists_returns_true_when_ticker_exists(
            self, ticker_repo: TickerRepository
    ) -> None:
        """exists 메서드 - 존재하는 경우 True."""
        # Given
        ticker_repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value))

        # When & Then
        assert ticker_repo.exists("KRW-BTC") is True

    def test_exists_returns_false_when_ticker_not_exists(
            self, ticker_repo: TickerRepository
    ) -> None:
        """exists 메서드 - 존재하지 않는 경우 False."""
        # When & Then
        assert ticker_repo.exists("KRW-BTC") is False

    def test_delete_by_id_removes_ticker(
            self, ticker_repo: TickerRepository
    ) -> None:
        """delete_by_id로 Ticker 삭제."""
        # Given
        ticker = Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value)
        saved = ticker_repo.save(ticker)

        # When
        result = ticker_repo.delete_by_id(saved.id)

        # Then
        assert result is True
        assert ticker_repo.find_by_ticker("KRW-BTC") is None

    def test_delete_by_id_returns_false_when_not_found(
            self, ticker_repo: TickerRepository
    ) -> None:
        """delete_by_id - 존재하지 않는 ID면 False 반환."""
        # When
        result = ticker_repo.delete_by_id(9999)

        # Then
        assert result is False

    def test_find_all_returns_all_tickers(
            self, ticker_repo: TickerRepository
    ) -> None:
        """find_all로 모든 Ticker 조회."""
        # Given
        ticker_repo.save(Ticker(ticker="KRW-BTC", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value))
        ticker_repo.save(Ticker(ticker="KRW-ETH", asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value))
        ticker_repo.save(Ticker(ticker="005930", asset_type=AssetType.KR_STOCK, data_source=DataSource.UPBIT.value))

        # When
        result = ticker_repo.find_all()

        # Then
        assert len(result) == 3
