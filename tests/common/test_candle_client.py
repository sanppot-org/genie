"""CandleInterval 및 CandleClient Protocol 테스트."""

from datetime import datetime

import pandas as pd

from src.common.candle_client import CandleClient, CandleInterval


class TestCandleInterval:
    """CandleInterval enum 테스트."""

    def test_minute_1_value(self) -> None:
        """1분봉 값 확인."""
        assert CandleInterval.MINUTE_1.value == "1m"

    def test_minute_5_value(self) -> None:
        """5분봉 값 확인."""
        assert CandleInterval.MINUTE_5.value == "5m"

    def test_minute_10_value(self) -> None:
        """10분봉 값 확인."""
        assert CandleInterval.MINUTE_10.value == "10m"

    def test_minute_30_value(self) -> None:
        """30분봉 값 확인."""
        assert CandleInterval.MINUTE_30.value == "30m"

    def test_hour_1_value(self) -> None:
        """1시간봉 값 확인."""
        assert CandleInterval.HOUR_1.value == "1h"

    def test_hour_4_value(self) -> None:
        """4시간봉 값 확인."""
        assert CandleInterval.HOUR_4.value == "4h"

    def test_day_value(self) -> None:
        """일봉 값 확인."""
        assert CandleInterval.DAY.value == "1d"

    def test_week_value(self) -> None:
        """주봉 값 확인."""
        assert CandleInterval.WEEK.value == "1w"

    def test_month_value(self) -> None:
        """월봉 값 확인."""
        assert CandleInterval.MONTH.value == "1M"

    def test_is_str_enum(self) -> None:
        """str과 호환되는지 확인."""
        assert isinstance(CandleInterval.DAY, str)
        assert CandleInterval.DAY == "1d"

    def test_all_intervals_exist(self) -> None:
        """모든 필수 간격이 정의되어 있는지 확인."""
        expected = [
            "MINUTE_1",
            "MINUTE_5",
            "MINUTE_10",
            "MINUTE_30",
            "HOUR_1",
            "HOUR_4",
            "DAY",
            "WEEK",
            "MONTH",
        ]
        actual = [interval.name for interval in CandleInterval]
        for name in expected:
            assert name in actual, f"{name}이 CandleInterval에 없습니다"


class TestCandleClientProtocol:
    """CandleClient Protocol 테스트."""

    def test_protocol_has_get_candles_method(self) -> None:
        """get_candles 메서드가 정의되어 있는지 확인."""
        assert hasattr(CandleClient, "get_candles")

    def test_protocol_has_supported_intervals_property(self) -> None:
        """supported_intervals 프로퍼티가 정의되어 있는지 확인."""
        assert hasattr(CandleClient, "supported_intervals")

    def test_mock_client_satisfies_protocol(self) -> None:
        """Mock 객체가 Protocol을 만족하는지 확인."""

        # Protocol을 만족하는 Mock 클래스 생성
        class MockCandleClient:
            def get_candles(
                    self,
                    symbol: str,
                    interval: CandleInterval,
                    count: int = 100,
                    end_time: datetime | None = None,
            ) -> pd.DataFrame:
                return pd.DataFrame()

            @property
            def supported_intervals(self) -> list[CandleInterval]:
                return [CandleInterval.DAY]

        mock_client = MockCandleClient()

        # Protocol 메서드 호출 가능 확인
        df = mock_client.get_candles("KRW-BTC", CandleInterval.DAY)
        assert isinstance(df, pd.DataFrame)

        intervals = mock_client.supported_intervals
        assert isinstance(intervals, list)

    def test_get_candles_returns_dataframe_with_ohlcv(self) -> None:
        """get_candles가 OHLCV 컬럼을 포함한 DataFrame을 반환하는지 확인."""

        class MockCandleClient:
            def get_candles(
                    self,
                    symbol: str,
                    interval: CandleInterval,
                    count: int = 100,
                    end_time: datetime | None = None,
            ) -> pd.DataFrame:
                return pd.DataFrame(
                    {
                        "open": [100.0],
                        "high": [110.0],
                        "low": [90.0],
                        "close": [105.0],
                        "volume": [1000.0],
                    },
                    index=pd.DatetimeIndex([datetime(2024, 1, 1)], tz="UTC"),
                )

            @property
            def supported_intervals(self) -> list[CandleInterval]:
                return [CandleInterval.DAY]

        client = MockCandleClient()
        df = client.get_candles("KRW-BTC", CandleInterval.DAY)

        # OHLCV 컬럼 확인
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns

        # UTC 인덱스 확인
        assert df.index.tz is not None
        assert str(df.index.tz) == "UTC"
