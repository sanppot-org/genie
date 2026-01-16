"""BinanceCandleClient 테스트."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.common.candle_client import CandleClient, CandleInterval
from src.providers.binance_candle_client import BinanceCandleClient
from util.binance.binance_api import BinanceAPI
from util.binance.model.candle import BinanceCandleData, BinanceCandleInterval


class TestBinanceCandleClientProtocol:
    """BinanceCandleClient가 CandleClient Protocol을 만족하는지 테스트."""

    def test_is_candle_client(self) -> None:
        """CandleClient Protocol을 만족하는지 확인."""
        mock_api = MagicMock(spec=BinanceAPI)
        client = BinanceCandleClient(mock_api)

        assert isinstance(client, CandleClient)

    def test_has_get_candles_method(self) -> None:
        """get_candles 메서드가 있는지 확인."""
        mock_api = MagicMock(spec=BinanceAPI)
        client = BinanceCandleClient(mock_api)

        assert hasattr(client, "get_candles")
        assert callable(client.get_candles)

    def test_has_supported_intervals_property(self) -> None:
        """supported_intervals 프로퍼티가 있는지 확인."""
        mock_api = MagicMock(spec=BinanceAPI)
        client = BinanceCandleClient(mock_api)

        assert hasattr(client, "supported_intervals")
        intervals = client.supported_intervals
        assert isinstance(intervals, list)


class TestBinanceCandleClientIntervalMapping:
    """CandleInterval → BinanceCandleInterval 변환 테스트."""

    @pytest.fixture
    def client(self) -> BinanceCandleClient:
        mock_api = MagicMock(spec=BinanceAPI)
        mock_api.get_candles.return_value = []
        return BinanceCandleClient(mock_api)

    def test_minute_1_mapping(self, client: BinanceCandleClient) -> None:
        """MINUTE_1 → BinanceCandleInterval.MINUTE_1 변환."""
        result = client._to_binance_interval(CandleInterval.MINUTE_1)
        assert result == BinanceCandleInterval.MINUTE_1

    def test_minute_5_mapping(self, client: BinanceCandleClient) -> None:
        """MINUTE_5 → BinanceCandleInterval.MINUTE_5 변환."""
        result = client._to_binance_interval(CandleInterval.MINUTE_5)
        assert result == BinanceCandleInterval.MINUTE_5

    def test_minute_30_mapping(self, client: BinanceCandleClient) -> None:
        """MINUTE_30 → BinanceCandleInterval.MINUTE_30 변환."""
        result = client._to_binance_interval(CandleInterval.MINUTE_30)
        assert result == BinanceCandleInterval.MINUTE_30

    def test_hour_1_mapping(self, client: BinanceCandleClient) -> None:
        """HOUR_1 → BinanceCandleInterval.HOUR_1 변환."""
        result = client._to_binance_interval(CandleInterval.HOUR_1)
        assert result == BinanceCandleInterval.HOUR_1

    def test_hour_4_mapping(self, client: BinanceCandleClient) -> None:
        """HOUR_4 → BinanceCandleInterval.HOUR_4 변환."""
        result = client._to_binance_interval(CandleInterval.HOUR_4)
        assert result == BinanceCandleInterval.HOUR_4

    def test_day_mapping(self, client: BinanceCandleClient) -> None:
        """DAY → BinanceCandleInterval.DAY_1 변환."""
        result = client._to_binance_interval(CandleInterval.DAY)
        assert result == BinanceCandleInterval.DAY_1

    def test_week_mapping(self, client: BinanceCandleClient) -> None:
        """WEEK → BinanceCandleInterval.WEEK_1 변환."""
        result = client._to_binance_interval(CandleInterval.WEEK)
        assert result == BinanceCandleInterval.WEEK_1

    def test_month_mapping(self, client: BinanceCandleClient) -> None:
        """MONTH → BinanceCandleInterval.MONTH_1 변환."""
        result = client._to_binance_interval(CandleInterval.MONTH)
        assert result == BinanceCandleInterval.MONTH_1

    def test_minute_10_not_supported(self, client: BinanceCandleClient) -> None:
        """MINUTE_10은 Binance에서 지원하지 않음."""
        with pytest.raises(ValueError):
            client._to_binance_interval(CandleInterval.MINUTE_10)


class TestBinanceCandleClientGetCandles:
    """get_candles 메서드 테스트."""

    def test_get_candles_calls_api_with_correct_params(self) -> None:
        """API가 올바른 파라미터로 호출되는지 확인."""
        mock_api = MagicMock(spec=BinanceAPI)
        mock_api.get_candles.return_value = []
        client = BinanceCandleClient(mock_api)

        end_time = datetime(2024, 1, 1, tzinfo=UTC)
        client.get_candles(
            symbol="BTCUSDT",
            interval=CandleInterval.DAY,
            count=100,
            end_time=end_time,
        )

        mock_api.get_candles.assert_called_once_with(
            symbol="BTCUSDT",
            interval=BinanceCandleInterval.DAY_1,
            limit=100,
            end_time=end_time,
        )

    def test_get_candles_returns_standardized_dataframe(self) -> None:
        """표준화된 DataFrame이 반환되는지 확인."""
        mock_api = MagicMock(spec=BinanceAPI)

        # Mock 캔들 데이터
        mock_candle = BinanceCandleData(
            open_time=datetime(2024, 1, 1, tzinfo=UTC),
            open_price=100.0,
            high_price=110.0,
            low_price=90.0,
            close_price=105.0,
            volume=1000.0,
            close_time=datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC),
            quote_asset_volume=100000.0,
            number_of_trades=500,
            taker_buy_base_volume=500.0,
            taker_buy_quote_volume=50000.0,
        )
        mock_api.get_candles.return_value = [mock_candle]
        client = BinanceCandleClient(mock_api)

        result = client.get_candles("BTCUSDT", CandleInterval.DAY, count=1)

        # timestamp, local_time, OHLCV 컬럼 확인
        assert list(result.columns) == [
            "timestamp", "local_time", "open", "high", "low", "close", "volume"
        ]

        # UTC 인덱스
        assert result.index.tz is not None
        assert str(result.index.tz) == "UTC"

        # 값 확인
        assert result.iloc[0]["open"] == 100.0
        assert result.iloc[0]["close"] == 105.0

    def test_get_candles_empty_response(self) -> None:
        """빈 응답 처리 확인."""
        mock_api = MagicMock(spec=BinanceAPI)
        mock_api.get_candles.return_value = []
        client = BinanceCandleClient(mock_api)

        result = client.get_candles("BTCUSDT", CandleInterval.DAY)

        assert result.empty


class TestBinanceCandleClientSupportedIntervals:
    """supported_intervals 프로퍼티 테스트."""

    def test_supported_intervals_contains_expected(self) -> None:
        """기대하는 간격이 포함되어 있는지 확인."""
        mock_api = MagicMock(spec=BinanceAPI)
        client = BinanceCandleClient(mock_api)

        intervals = client.supported_intervals

        expected = [
            CandleInterval.MINUTE_1,
            CandleInterval.MINUTE_5,
            CandleInterval.MINUTE_30,
            CandleInterval.HOUR_1,
            CandleInterval.HOUR_4,
            CandleInterval.DAY,
            CandleInterval.WEEK,
            CandleInterval.MONTH,
        ]

        for interval in expected:
            assert interval in intervals, f"{interval}이 supported_intervals에 없습니다"

    def test_minute_10_not_supported(self) -> None:
        """MINUTE_10은 지원하지 않음."""
        mock_api = MagicMock(spec=BinanceAPI)
        client = BinanceCandleClient(mock_api)

        intervals = client.supported_intervals

        assert CandleInterval.MINUTE_10 not in intervals
