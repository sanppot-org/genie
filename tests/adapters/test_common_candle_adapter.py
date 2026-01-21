"""Tests for CommonCandleAdapter."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from src.adapters.candle_adapters import CommonCandleAdapter
from src.common.candle_client import CandleInterval
from src.database.models import CandleMinute1


class TestCommonCandleAdapterToMinute1Models:
    """CommonCandleAdapter._to_minute1_models 테스트."""

    @pytest.fixture
    def adapter(self) -> CommonCandleAdapter:
        """CommonCandleAdapter fixture."""
        return CommonCandleAdapter()

    @pytest.fixture
    def sample_common_df(self) -> pd.DataFrame:
        """CommonCandleSchema를 따르는 샘플 DataFrame."""
        return pd.DataFrame({
            "timestamp": [
                datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
                datetime(2024, 1, 1, 10, 1, tzinfo=UTC),
            ],
            "local_time": [
                datetime(2024, 1, 1, 19, 0),
                datetime(2024, 1, 1, 19, 1),
            ],
            "open": [50000000.0, 50100000.0],
            "high": [51000000.0, 51100000.0],
            "low": [49000000.0, 49100000.0],
            "close": [50500000.0, 50600000.0],
            "volume": [10.5, 11.0],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 10:00:00", tz="UTC"),
            pd.Timestamp("2024-01-01 10:01:00", tz="UTC"),
        ]))

    def test_converts_dataframe_to_candle_minute1_models(
            self,
            adapter: CommonCandleAdapter,
            sample_common_df: pd.DataFrame,
    ):
        """CommonCandleSchema DataFrame을 CandleMinute1 모델 리스트로 변환한다."""
        # Given
        ticker_id = 1

        # When
        models = adapter.to_candle_models(
            sample_common_df, ticker_id, CandleInterval.MINUTE_1
        )

        # Then
        assert len(models) == 2
        assert all(isinstance(m, CandleMinute1) for m in models)

    def test_model_has_correct_ticker_id(
            self,
            adapter: CommonCandleAdapter,
            sample_common_df: pd.DataFrame,
    ):
        """변환된 모델은 올바른 ticker_id를 가진다."""
        # Given
        ticker_id = 42

        # When
        models = adapter.to_candle_models(
            sample_common_df, ticker_id, CandleInterval.MINUTE_1
        )

        # Then
        assert all(m.ticker_id == ticker_id for m in models)

    def test_model_has_correct_timestamp(
            self,
            adapter: CommonCandleAdapter,
            sample_common_df: pd.DataFrame,
    ):
        """변환된 모델은 올바른 timestamp를 가진다."""
        # Given
        ticker_id = 1

        # When
        models = adapter.to_candle_models(
            sample_common_df, ticker_id, CandleInterval.MINUTE_1
        )

        # Then
        assert models[0].timestamp == datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        assert models[1].timestamp == datetime(2024, 1, 1, 10, 1, tzinfo=UTC)

    def test_model_has_correct_local_time(
            self,
            adapter: CommonCandleAdapter,
            sample_common_df: pd.DataFrame,
    ):
        """변환된 모델은 올바른 local_time을 가진다."""
        # Given
        ticker_id = 1

        # When
        models = adapter.to_candle_models(
            sample_common_df, ticker_id, CandleInterval.MINUTE_1
        )

        # Then
        assert models[0].local_time == datetime(2024, 1, 1, 19, 0)
        assert models[1].local_time == datetime(2024, 1, 1, 19, 1)

    def test_model_has_correct_ohlcv(
            self,
            adapter: CommonCandleAdapter,
            sample_common_df: pd.DataFrame,
    ):
        """변환된 모델은 올바른 OHLCV 값을 가진다."""
        # Given
        ticker_id = 1

        # When
        models = adapter.to_candle_models(
            sample_common_df, ticker_id, CandleInterval.MINUTE_1
        )

        # Then
        first = models[0]
        assert first.open == 50000000.0
        assert first.high == 51000000.0
        assert first.low == 49000000.0
        assert first.close == 50500000.0
        assert first.volume == 10.5

    def test_returns_empty_list_for_empty_dataframe(
            self,
            adapter: CommonCandleAdapter,
    ):
        """빈 DataFrame은 빈 리스트를 반환한다."""
        # Given
        empty_df = pd.DataFrame(columns=[
            "timestamp", "local_time", "open", "high", "low", "close", "volume"
        ])
        ticker_id = 1

        # When
        models = adapter.to_candle_models(
            empty_df, ticker_id, CandleInterval.MINUTE_1
        )

        # Then
        assert models == []


class TestCommonCandleAdapterIntervalValidation:
    """CommonCandleAdapter interval 검증 테스트."""

    @pytest.fixture
    def adapter(self) -> CommonCandleAdapter:
        """CommonCandleAdapter fixture."""
        return CommonCandleAdapter()

    @pytest.fixture
    def sample_df(self) -> pd.DataFrame:
        """샘플 DataFrame."""
        return pd.DataFrame({
            "timestamp": [datetime(2024, 1, 1, 10, 0, tzinfo=UTC)],
            "local_time": [datetime(2024, 1, 1, 19, 0)],
            "open": [50000000.0],
            "high": [51000000.0],
            "low": [49000000.0],
            "close": [50500000.0],
            "volume": [10.5],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 10:00:00", tz="UTC"),
        ]))

    def test_raises_type_error_for_non_candle_interval(
            self,
            adapter: CommonCandleAdapter,
            sample_df: pd.DataFrame,
    ):
        """CandleInterval이 아닌 interval은 TypeError를 발생시킨다."""
        # Given
        invalid_interval = "minute1"  # 문자열

        # When / Then
        with pytest.raises(TypeError, match="Expected CandleInterval"):
            adapter.to_candle_models(sample_df, 1, invalid_interval)

    def test_raises_value_error_for_unsupported_interval(
            self,
            adapter: CommonCandleAdapter,
            sample_df: pd.DataFrame,
    ):
        """지원하지 않는 CandleInterval은 ValueError를 발생시킨다."""
        # Given
        unsupported_interval = CandleInterval.WEEK  # 주봉은 미지원

        # When / Then
        with pytest.raises(ValueError, match="Unsupported interval"):
            adapter.to_candle_models(sample_df, 1, unsupported_interval)
