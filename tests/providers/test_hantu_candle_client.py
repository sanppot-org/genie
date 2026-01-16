"""HantuCandleClient 테스트."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.common.candle_client import CandleClient, CandleInterval
from src.hantu.model.overseas.candle_period import OverseasCandlePeriod
from src.hantu.model.overseas.minute_interval import OverseasMinuteInterval
from src.hantu.overseas_api import HantuOverseasAPI
from src.providers.hantu_candle_client import HantuCandleClient


class TestHantuCandleClientProtocol:
    """HantuCandleClient가 CandleClient Protocol을 만족하는지 테스트."""

    def test_is_candle_client(self) -> None:
        """CandleClient Protocol을 만족하는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuCandleClient(mock_api)

        assert isinstance(client, CandleClient)

    def test_has_get_candles_method(self) -> None:
        """get_candles 메서드가 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuCandleClient(mock_api)

        assert hasattr(client, "get_candles")
        assert callable(client.get_candles)

    def test_has_supported_intervals_property(self) -> None:
        """supported_intervals 프로퍼티가 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuCandleClient(mock_api)

        assert hasattr(client, "supported_intervals")
        intervals = client.supported_intervals
        assert isinstance(intervals, list)


class TestHantuCandleClientIntervalMapping:
    """CandleInterval 변환 테스트."""

    @pytest.fixture
    def client(self) -> HantuCandleClient:
        mock_api = MagicMock(spec=HantuOverseasAPI)
        return HantuCandleClient(mock_api)

    def test_minute_1_is_minute_interval(self, client: HantuCandleClient) -> None:
        """MINUTE_1은 분봉 타입으로 분류."""
        assert client._is_minute_interval(CandleInterval.MINUTE_1)

    def test_minute_5_is_minute_interval(self, client: HantuCandleClient) -> None:
        """MINUTE_5은 분봉 타입으로 분류."""
        assert client._is_minute_interval(CandleInterval.MINUTE_5)

    def test_hour_1_is_minute_interval(self, client: HantuCandleClient) -> None:
        """HOUR_1은 분봉 타입으로 분류 (MIN_60)."""
        assert client._is_minute_interval(CandleInterval.HOUR_1)

    def test_day_is_not_minute_interval(self, client: HantuCandleClient) -> None:
        """DAY는 일봉 타입으로 분류."""
        assert not client._is_minute_interval(CandleInterval.DAY)

    def test_to_minute_interval_mapping(self, client: HantuCandleClient) -> None:
        """분봉 간격 변환 테스트."""
        assert client._to_minute_interval(CandleInterval.MINUTE_1) == OverseasMinuteInterval.MIN_1
        assert client._to_minute_interval(CandleInterval.MINUTE_5) == OverseasMinuteInterval.MIN_5
        assert client._to_minute_interval(CandleInterval.MINUTE_10) == OverseasMinuteInterval.MIN_10
        assert client._to_minute_interval(CandleInterval.MINUTE_30) == OverseasMinuteInterval.MIN_30
        assert client._to_minute_interval(CandleInterval.HOUR_1) == OverseasMinuteInterval.MIN_60

    def test_to_daily_period_mapping(self, client: HantuCandleClient) -> None:
        """일봉 기간 변환 테스트."""
        assert client._to_daily_period(CandleInterval.DAY) == OverseasCandlePeriod.DAILY
        assert client._to_daily_period(CandleInterval.WEEK) == OverseasCandlePeriod.WEEKLY
        assert client._to_daily_period(CandleInterval.MONTH) == OverseasCandlePeriod.MONTHLY


class TestHantuCandleClientGetCandles:
    """get_candles 메서드 테스트."""

    def test_get_minute_candles_calls_api(self) -> None:
        """분봉 조회 시 get_minute_candles API 호출."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuCandleClient(mock_api)
        client.get_candles(
            symbol="AAPL",
            interval=CandleInterval.MINUTE_1,
            count=100,
        )

        mock_api.get_minute_candles.assert_called_once()

    def test_get_daily_candles_calls_api(self) -> None:
        """일봉 조회 시 get_daily_candles API 호출."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output1 = []
        mock_api.get_daily_candles.return_value = mock_response

        client = HantuCandleClient(mock_api)
        end_time = datetime(2024, 1, 31, tzinfo=UTC)
        client.get_candles(
            symbol="AAPL",
            interval=CandleInterval.DAY,
            count=100,
            end_time=end_time,
        )

        mock_api.get_daily_candles.assert_called_once()

    def test_get_candles_returns_standardized_dataframe(self) -> None:
        """표준화된 DataFrame이 반환되는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # Mock 분봉 응답
        mock_candle = MagicMock()
        mock_candle.xymd = "20240101"  # 일자
        mock_candle.xhms = "093000"  # 시간
        mock_candle.open = "100.0"
        mock_candle.high = "110.0"
        mock_candle.low = "90.0"
        mock_candle.last = "105.0"
        mock_candle.evol = "1000"

        mock_response = MagicMock()
        mock_response.output2 = [mock_candle]
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.MINUTE_1, count=1)

        # timestamp, local_time, OHLCV 컬럼 확인
        assert "timestamp" in result.columns
        assert "local_time" in result.columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns

    def test_get_candles_empty_response(self) -> None:
        """빈 응답 처리 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.MINUTE_1)

        assert result.empty


class TestHantuCandleClientSupportedIntervals:
    """supported_intervals 프로퍼티 테스트."""

    def test_supported_intervals_contains_minute_intervals(self) -> None:
        """분봉 간격이 포함되어 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuCandleClient(mock_api)

        intervals = client.supported_intervals

        assert CandleInterval.MINUTE_1 in intervals
        assert CandleInterval.MINUTE_5 in intervals
        assert CandleInterval.MINUTE_10 in intervals
        assert CandleInterval.MINUTE_30 in intervals
        assert CandleInterval.HOUR_1 in intervals

    def test_supported_intervals_contains_daily_intervals(self) -> None:
        """일봉 간격이 포함되어 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuCandleClient(mock_api)

        intervals = client.supported_intervals

        assert CandleInterval.DAY in intervals
        assert CandleInterval.WEEK in intervals
        assert CandleInterval.MONTH in intervals

    def test_hour_4_not_supported(self) -> None:
        """HOUR_4는 지원하지 않음."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuCandleClient(mock_api)

        intervals = client.supported_intervals

        assert CandleInterval.HOUR_4 not in intervals
