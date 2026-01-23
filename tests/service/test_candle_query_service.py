"""CandleQueryService 테스트."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.common.candle_client import CandleClient, CandleInterval
from src.common.data_adapter import DataSource
from src.database.models import Ticker
from src.service.candle_query_service import CandleQueryService


def _create_mock_ticker(ticker_code: str, data_source: DataSource) -> MagicMock:
    """Mock Ticker 생성 헬퍼."""
    mock_ticker = MagicMock(spec=Ticker)
    mock_ticker.ticker = ticker_code
    mock_ticker.data_source = data_source  # DataSource enum 직접 설정
    return mock_ticker


class TestCandleQueryServiceBasic:
    """CandleQueryService 기본 테스트."""

    def test_get_candles_with_upbit_ticker(self) -> None:
        """Upbit Ticker로 캔들 조회."""
        mock_client = MagicMock(spec=CandleClient)
        expected_df = pd.DataFrame(
            {"open": [100.0], "close": [105.0]},
            index=pd.DatetimeIndex([datetime(2024, 1, 1, tzinfo=UTC)]),
        )
        mock_client.get_candles.return_value = expected_df

        service = CandleQueryService({DataSource.UPBIT: mock_client})
        mock_ticker = _create_mock_ticker("KRW-BTC", DataSource.UPBIT)

        result = service.get_candles(
            ticker=mock_ticker,
            interval=CandleInterval.DAY,
            count=100,
        )

        mock_client.get_candles.assert_called_once_with(
            symbol="KRW-BTC",
            interval=CandleInterval.DAY,
            count=100,
            end_time=None,
        )
        assert result.equals(expected_df)

    def test_get_candles_with_binance_ticker(self) -> None:
        """Binance Ticker로 캔들 조회."""
        mock_client = MagicMock(spec=CandleClient)
        expected_df = pd.DataFrame(
            {"open": [50000.0], "close": [51000.0]},
            index=pd.DatetimeIndex([datetime(2024, 1, 1, tzinfo=UTC)]),
        )
        mock_client.get_candles.return_value = expected_df

        service = CandleQueryService({DataSource.BINANCE: mock_client})
        mock_ticker = _create_mock_ticker("BTCUSDT", DataSource.BINANCE)

        result = service.get_candles(
            ticker=mock_ticker,
            interval=CandleInterval.HOUR_1,
            count=50,
        )

        mock_client.get_candles.assert_called_once_with(
            symbol="BTCUSDT",
            interval=CandleInterval.HOUR_1,
            count=50,
            end_time=None,
        )
        assert result.equals(expected_df)

    def test_get_candles_with_end_time(self) -> None:
        """end_time 파라미터 전달 - UTC aware datetime은 naive로 변환되어 전달."""
        mock_client = MagicMock(spec=CandleClient)
        mock_client.get_candles.return_value = pd.DataFrame()

        service = CandleQueryService({DataSource.UPBIT: mock_client})
        mock_ticker = _create_mock_ticker("KRW-BTC", DataSource.UPBIT)
        end_time = datetime(2024, 1, 31, tzinfo=UTC)

        service.get_candles(
            ticker=mock_ticker,
            interval=CandleInterval.DAY,
            count=100,
            end_time=end_time,
        )

        # UTC aware datetime은 naive datetime으로 변환되어 전달됨
        expected_end_time = datetime(2024, 1, 31)  # naive
        mock_client.get_candles.assert_called_once_with(
            symbol="KRW-BTC",
            interval=CandleInterval.DAY,
            count=100,
            end_time=expected_end_time,
        )

    def test_get_candles_unknown_source_raises_error(self) -> None:
        """등록되지 않은 소스의 Ticker 사용 시 에러."""
        mock_client = MagicMock(spec=CandleClient)
        service = CandleQueryService({DataSource.UPBIT: mock_client})
        mock_ticker = _create_mock_ticker("BTCUSDT", DataSource.BINANCE)  # Binance는 등록 안 됨

        with pytest.raises(ValueError, match="등록되지 않은 데이터 소스"):
            service.get_candles(
                ticker=mock_ticker,
                interval=CandleInterval.DAY,
            )


class TestCandleQueryServiceMultipleSources:
    """다중 소스 테스트."""

    def test_multiple_sources_registered(self) -> None:
        """여러 소스 등록 및 사용."""
        upbit_client = MagicMock(spec=CandleClient)
        binance_client = MagicMock(spec=CandleClient)

        upbit_df = pd.DataFrame({"source": ["upbit"]})
        binance_df = pd.DataFrame({"source": ["binance"]})

        upbit_client.get_candles.return_value = upbit_df
        binance_client.get_candles.return_value = binance_df

        service = CandleQueryService({
            DataSource.UPBIT: upbit_client,
            DataSource.BINANCE: binance_client,
        })

        upbit_ticker = _create_mock_ticker("KRW-BTC", DataSource.UPBIT)
        binance_ticker = _create_mock_ticker("BTCUSDT", DataSource.BINANCE)

        result_upbit = service.get_candles(upbit_ticker, CandleInterval.DAY)
        result_binance = service.get_candles(binance_ticker, CandleInterval.DAY)

        assert result_upbit.equals(upbit_df)
        assert result_binance.equals(binance_df)


class TestCandleQueryServiceSupportedIntervals:
    """get_supported_intervals 테스트."""

    def test_get_supported_intervals(self) -> None:
        """특정 소스의 지원 간격 조회."""
        mock_client = MagicMock(spec=CandleClient)
        mock_client.supported_intervals = [
            CandleInterval.MINUTE_1,
            CandleInterval.DAY,
        ]

        service = CandleQueryService({DataSource.UPBIT: mock_client})
        result = service.get_supported_intervals(DataSource.UPBIT)

        assert CandleInterval.MINUTE_1 in result
        assert CandleInterval.DAY in result

    def test_get_supported_intervals_unknown_source(self) -> None:
        """등록되지 않은 소스의 지원 간격 조회 시 에러."""
        mock_client = MagicMock(spec=CandleClient)
        service = CandleQueryService({DataSource.UPBIT: mock_client})

        with pytest.raises(ValueError):
            service.get_supported_intervals(DataSource.BINANCE)


class TestCandleQueryServiceAvailableSources:
    """available_sources 테스트."""

    def test_available_sources(self) -> None:
        """등록된 소스 목록 조회."""
        upbit_client = MagicMock(spec=CandleClient)
        binance_client = MagicMock(spec=CandleClient)

        service = CandleQueryService({
            DataSource.UPBIT: upbit_client,
            DataSource.BINANCE: binance_client,
        })

        sources = service.available_sources

        assert DataSource.UPBIT in sources
        assert DataSource.BINANCE in sources
        assert len(sources) == 2


class TestCandleQueryServiceTimezoneNormalization:
    """end_time 타임존 정규화 테스트."""

    def test_get_candles_converts_timezone_aware_end_time_to_utc_naive(self) -> None:
        """timezone-aware end_time이 UTC naive datetime으로 변환되어 client에 전달되는지 확인."""
        from zoneinfo import ZoneInfo

        mock_client = MagicMock(spec=CandleClient)
        mock_client.get_candles.return_value = pd.DataFrame()

        service = CandleQueryService({DataSource.UPBIT: mock_client})
        mock_ticker = _create_mock_ticker("KRW-BTC", DataSource.UPBIT)

        # Given: KST 시간 (UTC+9)
        kst_time = datetime(2024, 1, 15, 18, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        # When: get_candles 호출
        service.get_candles(
            ticker=mock_ticker,
            interval=CandleInterval.MINUTE_1,
            count=100,
            end_time=kst_time,
        )

        # Then: client에는 UTC naive datetime으로 전달
        expected_utc = datetime(2024, 1, 15, 9, 0, 0)  # KST 18:00 = UTC 09:00
        mock_client.get_candles.assert_called_once_with(
            symbol="KRW-BTC",
            interval=CandleInterval.MINUTE_1,
            count=100,
            end_time=expected_utc,
        )

    def test_get_candles_converts_utc_aware_end_time_to_utc_naive(self) -> None:
        """UTC timezone-aware end_time이 naive datetime으로 변환되어 전달."""
        mock_client = MagicMock(spec=CandleClient)
        mock_client.get_candles.return_value = pd.DataFrame()

        service = CandleQueryService({DataSource.UPBIT: mock_client})
        mock_ticker = _create_mock_ticker("KRW-BTC", DataSource.UPBIT)

        # Given: UTC aware datetime
        utc_aware_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)

        # When: get_candles 호출
        service.get_candles(
            ticker=mock_ticker,
            interval=CandleInterval.MINUTE_1,
            end_time=utc_aware_time,
        )

        # Then: client에는 UTC naive datetime으로 전달
        expected_utc = datetime(2024, 1, 15, 9, 0, 0)  # naive
        mock_client.get_candles.assert_called_once()
        actual_end_time = mock_client.get_candles.call_args.kwargs["end_time"]
        assert actual_end_time == expected_utc
        assert actual_end_time.tzinfo is None

    def test_get_candles_keeps_naive_datetime_as_is(self) -> None:
        """naive datetime은 그대로 전달 (UTC로 가정)."""
        mock_client = MagicMock(spec=CandleClient)
        mock_client.get_candles.return_value = pd.DataFrame()

        service = CandleQueryService({DataSource.UPBIT: mock_client})
        mock_ticker = _create_mock_ticker("KRW-BTC", DataSource.UPBIT)

        # Given: naive datetime
        naive_time = datetime(2024, 1, 15, 9, 0, 0)

        # When: get_candles 호출
        service.get_candles(
            ticker=mock_ticker,
            interval=CandleInterval.MINUTE_1,
            end_time=naive_time,
        )

        # Then: 그대로 전달
        mock_client.get_candles.assert_called_once()
        actual_end_time = mock_client.get_candles.call_args.kwargs["end_time"]
        assert actual_end_time == naive_time
        assert actual_end_time.tzinfo is None

    def test_get_candles_none_end_time_stays_none(self) -> None:
        """None end_time은 그대로 None 전달."""
        mock_client = MagicMock(spec=CandleClient)
        mock_client.get_candles.return_value = pd.DataFrame()

        service = CandleQueryService({DataSource.UPBIT: mock_client})
        mock_ticker = _create_mock_ticker("KRW-BTC", DataSource.UPBIT)

        # When: end_time 없이 호출
        service.get_candles(
            ticker=mock_ticker,
            interval=CandleInterval.MINUTE_1,
        )

        # Then: None 전달
        mock_client.get_candles.assert_called_once()
        actual_end_time = mock_client.get_candles.call_args.kwargs["end_time"]
        assert actual_end_time is None
