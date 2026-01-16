"""UpbitCandleClient 테스트."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.common.candle_client import CandleClient, CandleInterval
from src.providers.upbit_candle_client import UpbitCandleClient
from src.upbit.upbit_api import UpbitAPI, UpbitCandleInterval


class TestUpbitCandleClientProtocol:
    """UpbitCandleClient가 CandleClient Protocol을 만족하는지 테스트."""

    def test_is_candle_client(self) -> None:
        """CandleClient Protocol을 만족하는지 확인."""
        mock_api = MagicMock(spec=UpbitAPI)
        client = UpbitCandleClient(mock_api)

        # runtime_checkable Protocol 확인
        assert isinstance(client, CandleClient)

    def test_has_get_candles_method(self) -> None:
        """get_candles 메서드가 있는지 확인."""
        mock_api = MagicMock(spec=UpbitAPI)
        client = UpbitCandleClient(mock_api)

        assert hasattr(client, "get_candles")
        assert callable(client.get_candles)

    def test_has_supported_intervals_property(self) -> None:
        """supported_intervals 프로퍼티가 있는지 확인."""
        mock_api = MagicMock(spec=UpbitAPI)
        client = UpbitCandleClient(mock_api)

        assert hasattr(client, "supported_intervals")
        intervals = client.supported_intervals
        assert isinstance(intervals, list)


class TestUpbitCandleClientIntervalMapping:
    """CandleInterval → UpbitCandleInterval 변환 테스트."""

    @pytest.fixture
    def client(self) -> UpbitCandleClient:
        mock_api = MagicMock(spec=UpbitAPI)
        mock_api.get_candles.return_value = pd.DataFrame()
        return UpbitCandleClient(mock_api)

    def test_minute_1_mapping(self, client: UpbitCandleClient) -> None:
        """MINUTE_1 → UpbitCandleInterval.MINUTE_1 변환."""
        result = client._to_upbit_interval(CandleInterval.MINUTE_1)
        assert result == UpbitCandleInterval.MINUTE_1

    def test_minute_5_mapping(self, client: UpbitCandleClient) -> None:
        """MINUTE_5 → UpbitCandleInterval.MINUTE_5 변환."""
        result = client._to_upbit_interval(CandleInterval.MINUTE_5)
        assert result == UpbitCandleInterval.MINUTE_5

    def test_hour_1_mapping(self, client: UpbitCandleClient) -> None:
        """HOUR_1 → UpbitCandleInterval.MINUTE_60 변환."""
        result = client._to_upbit_interval(CandleInterval.HOUR_1)
        assert result == UpbitCandleInterval.MINUTE_60

    def test_hour_4_mapping(self, client: UpbitCandleClient) -> None:
        """HOUR_4 → UpbitCandleInterval.MINUTE_240 변환."""
        result = client._to_upbit_interval(CandleInterval.HOUR_4)
        assert result == UpbitCandleInterval.MINUTE_240

    def test_day_mapping(self, client: UpbitCandleClient) -> None:
        """DAY → UpbitCandleInterval.DAY 변환."""
        result = client._to_upbit_interval(CandleInterval.DAY)
        assert result == UpbitCandleInterval.DAY

    def test_week_mapping(self, client: UpbitCandleClient) -> None:
        """WEEK → UpbitCandleInterval.WEEK 변환."""
        result = client._to_upbit_interval(CandleInterval.WEEK)
        assert result == UpbitCandleInterval.WEEK

    def test_month_mapping(self, client: UpbitCandleClient) -> None:
        """MONTH → UpbitCandleInterval.MONTH 변환."""
        result = client._to_upbit_interval(CandleInterval.MONTH)
        assert result == UpbitCandleInterval.MONTH


class TestUpbitCandleClientGetCandles:
    """get_candles 메서드 테스트."""

    def test_get_candles_calls_api_with_correct_params(self) -> None:
        """API가 올바른 파라미터로 호출되는지 확인."""
        mock_api = MagicMock(spec=UpbitAPI)
        mock_api.get_candles.return_value = pd.DataFrame()
        client = UpbitCandleClient(mock_api)

        end_time = datetime(2024, 1, 1, tzinfo=UTC)
        client.get_candles(
            symbol="KRW-BTC",
            interval=CandleInterval.DAY,
            count=100,
            end_time=end_time,
        )

        mock_api.get_candles.assert_called_once_with(
            market="KRW-BTC",
            interval=UpbitCandleInterval.DAY,
            count=100,
            to=end_time,
        )

    def test_get_candles_returns_standardized_dataframe(self) -> None:
        """표준화된 DataFrame이 반환되는지 확인."""
        mock_api = MagicMock(spec=UpbitAPI)
        # Upbit API 반환 형식 (KST index)
        mock_df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [110.0, 111.0],
                "low": [90.0, 91.0],
                "close": [105.0, 106.0],
                "volume": [1000.0, 1100.0],
                "value": [100000.0, 110000.0],
            },
            index=pd.DatetimeIndex(
                [datetime(2024, 1, 1, 9), datetime(2024, 1, 2, 9)],
                tz="Asia/Seoul",
            ),
        )
        mock_api.get_candles.return_value = mock_df
        client = UpbitCandleClient(mock_api)

        result = client.get_candles("KRW-BTC", CandleInterval.DAY, count=2)

        # timestamp, local_time, OHLCV 컬럼 포함
        assert list(result.columns) == [
            "timestamp", "local_time", "open", "high", "low", "close", "volume"
        ]

        # UTC 인덱스
        assert result.index.tz is not None
        assert str(result.index.tz) == "UTC"

        # timestamp는 UTC, local_time은 KST(naive)
        assert "timestamp" in result.columns
        assert "local_time" in result.columns

    def test_get_candles_empty_dataframe(self) -> None:
        """빈 DataFrame 처리 확인."""
        mock_api = MagicMock(spec=UpbitAPI)
        mock_api.get_candles.return_value = pd.DataFrame()
        client = UpbitCandleClient(mock_api)

        result = client.get_candles("KRW-BTC", CandleInterval.DAY)

        assert result.empty


class TestUpbitCandleClientSupportedIntervals:
    """supported_intervals 프로퍼티 테스트."""

    def test_supported_intervals_contains_all_mappable_intervals(self) -> None:
        """모든 매핑 가능한 간격이 포함되어 있는지 확인."""
        mock_api = MagicMock(spec=UpbitAPI)
        client = UpbitCandleClient(mock_api)

        intervals = client.supported_intervals

        expected = [
            CandleInterval.MINUTE_1,
            CandleInterval.MINUTE_5,
            CandleInterval.MINUTE_10,
            CandleInterval.MINUTE_30,
            CandleInterval.HOUR_1,
            CandleInterval.HOUR_4,
            CandleInterval.DAY,
            CandleInterval.WEEK,
            CandleInterval.MONTH,
        ]

        for interval in expected:
            assert interval in intervals, f"{interval}이 supported_intervals에 없습니다"
