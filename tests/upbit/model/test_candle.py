from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from src.upbit.model.candle import CandleSchema


class TestCandleSchema:
    """CandleSchema 테스트"""

    def test_candle_schema_validates_timezone_aware_timestamp(self):
        """timestamp가 timezone-aware datetime을 유지하는지 확인"""
        # Given: timezone-aware timestamp를 가진 DataFrame
        utc_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        kst_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        df = pd.DataFrame({
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
            "value": [100000.0],
            "timestamp": [utc_time],
        })
        df.index = pd.DatetimeIndex([kst_time])

        # When: CandleSchema로 validate
        validated_df = CandleSchema.validate(df)

        # Then: timestamp의 timezone 정보가 유지되어야 함
        assert validated_df["timestamp"].dt.tz is not None
        assert str(validated_df["timestamp"].dt.tz) == "UTC"

    def test_candle_schema_validates_timezone_aware_index(self):
        """index가 timezone-aware datetime을 유지하는지 확인"""
        # Given: timezone-aware index를 가진 DataFrame
        utc_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        kst_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        df = pd.DataFrame({
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
            "value": [100000.0],
            "timestamp": [utc_time],
        })
        df.index = pd.DatetimeIndex([kst_time])

        # When: CandleSchema로 validate
        validated_df = CandleSchema.validate(df)

        # Then: index의 timezone 정보가 유지되어야 함
        assert validated_df.index.tz is not None
        assert str(validated_df.index.tz) == "Asia/Seoul"
