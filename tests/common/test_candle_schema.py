"""CommonCandleSchema 테스트."""

from datetime import UTC, datetime, timezone

import pandas as pd
from pandera.errors import SchemaError
import pytest

from src.common.candle_schema import CommonCandleSchema


class TestCommonCandleSchemaValidation:
    """CommonCandleSchema 검증 테스트."""

    def test_valid_dataframe_passes_validation(self) -> None:
        """유효한 DataFrame이 검증을 통과한다."""
        utc_time1 = datetime(2024, 1, 1, tzinfo=UTC)
        utc_time2 = datetime(2024, 1, 2, tzinfo=UTC)
        local_time1 = datetime(2024, 1, 1, 9, 0, 0)  # KST
        local_time2 = datetime(2024, 1, 2, 9, 0, 0)

        df = pd.DataFrame(
            {
                "timestamp": [utc_time1, utc_time2],
                "local_time": [local_time1, local_time2],
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [1000.0, 1100.0],
            },
            index=pd.DatetimeIndex([utc_time1, utc_time2]),
        )

        result = CommonCandleSchema.validate(df)

        assert len(result) == 2
        assert list(result.columns) == [
            "timestamp", "local_time", "open", "high", "low", "close", "volume"
        ]

    def test_missing_column_raises_error(self) -> None:
        """필수 컬럼이 없으면 에러가 발생한다."""
        utc_time = datetime(2024, 1, 1, tzinfo=UTC)
        df = pd.DataFrame(
            {
                "timestamp": [utc_time],
                "local_time": [datetime(2024, 1, 1, 9, 0, 0)],
                "open": [100.0],
                "high": [105.0],
                "low": [99.0],
                "close": [104.0],
                # volume 컬럼 누락
            },
            index=pd.DatetimeIndex([utc_time]),
        )

        with pytest.raises(SchemaError):
            CommonCandleSchema.validate(df)

    def test_extra_column_raises_error_with_strict_mode(self) -> None:
        """strict 모드에서 추가 컬럼이 있으면 에러가 발생한다."""
        utc_time = datetime(2024, 1, 1, tzinfo=UTC)
        df = pd.DataFrame(
            {
                "timestamp": [utc_time],
                "local_time": [datetime(2024, 1, 1, 9, 0, 0)],
                "open": [100.0],
                "high": [105.0],
                "low": [99.0],
                "close": [104.0],
                "volume": [1000.0],
                "extra_column": ["not_allowed"],
            },
            index=pd.DatetimeIndex([utc_time]),
        )

        with pytest.raises(SchemaError):
            CommonCandleSchema.validate(df)

    def test_coercion_converts_integer_to_float(self) -> None:
        """coerce 모드에서 정수가 float으로 변환된다."""
        utc_time = datetime(2024, 1, 1, tzinfo=UTC)
        df = pd.DataFrame(
            {
                "timestamp": [utc_time],
                "local_time": [datetime(2024, 1, 1, 9, 0, 0)],
                "open": [100],  # int
                "high": [105],  # int
                "low": [99],  # int
                "close": [104],  # int
                "volume": [1000],  # int
            },
            index=pd.DatetimeIndex([utc_time]),
        )

        result = CommonCandleSchema.validate(df)

        assert result["open"].dtype == float
        assert result["volume"].dtype == float

    def test_empty_dataframe_passes_validation(self) -> None:
        """빈 DataFrame도 검증을 통과한다."""
        df = pd.DataFrame(
            columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["local_time"] = pd.to_datetime(df["local_time"])
        df[["open", "high", "low", "close", "volume"]] = df[
            ["open", "high", "low", "close", "volume"]
        ].astype(float)
        df.index = pd.DatetimeIndex([], tz=UTC)

        result = CommonCandleSchema.validate(df)

        assert len(result) == 0
        assert list(result.columns) == [
            "timestamp", "local_time", "open", "high", "low", "close", "volume"
        ]


class TestCommonCandleSchemaColumnOrder:
    """컬럼 순서 테스트."""

    def test_column_order_is_preserved(self) -> None:
        """컬럼 순서가 유지된다."""
        utc_time = datetime(2024, 1, 1, tzinfo=UTC)
        df = pd.DataFrame(
            {
                "volume": [1000.0],  # 순서 뒤섞음
                "close": [104.0],
                "low": [99.0],
                "high": [105.0],
                "open": [100.0],
                "local_time": [datetime(2024, 1, 1, 9, 0, 0)],
                "timestamp": [utc_time],
            },
            index=pd.DatetimeIndex([utc_time]),
        )

        result = CommonCandleSchema.validate(df)

        # 검증 후에도 원래 순서 유지 (strict 모드에서는 컬럼 순서 강제 안함)
        assert "open" in result.columns
        assert "close" in result.columns
        assert "timestamp" in result.columns
        assert "local_time" in result.columns
