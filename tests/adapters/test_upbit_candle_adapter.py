"""Tests for UpbitCandleAdapter.to_candle_models method."""

from datetime import datetime

import pandas as pd
from pandera.typing import DataFrame
import pytest
import pytz

from src.adapters.candle_adapters import UpbitCandleAdapter
from src.database.models import CandleDaily, CandleMinute1
from src.upbit.model.candle import CandleSchema
from src.upbit.upbit_api import UpbitCandleInterval as UpbitInterval


@pytest.fixture
def upbit_adapter() -> UpbitCandleAdapter:
    """UpbitCandleAdapter 인스턴스를 반환합니다."""
    return UpbitCandleAdapter()


@pytest.fixture
def sample_candle_df() -> DataFrame[CandleSchema]:
    """유효한 Upbit 캔들 DataFrame을 반환합니다.

    - 3개의 행
    - UTC timezone-aware DatetimeIndex (upbit_api.py에서 pd.to_datetime(..., utc=True) 사용)
    - 컬럼: open, high, low, close, volume, value
    """
    data = {
        "open": [100.0, 200.0, 300.0],
        "high": [110.0, 210.0, 310.0],
        "low": [90.0, 190.0, 290.0],
        "close": [105.0, 205.0, 305.0],
        "volume": [1000.0, 2000.0, 3000.0],
        "value": [105000.0, 410000.0, 915000.0],  # Upbit에만 있는 컬럼
    }
    index = pd.DatetimeIndex(
        [
            datetime(2024, 1, 1, 9, 0, 0, tzinfo=pytz.UTC),  # UTC 2024-01-01 09:00:00+00:00
            datetime(2024, 1, 1, 10, 0, 0, tzinfo=pytz.UTC),  # UTC 2024-01-01 10:00:00+00:00
            datetime(2024, 1, 1, 11, 0, 0, tzinfo=pytz.UTC),  # UTC 2024-01-01 11:00:00+00:00
        ]
    )
    df = pd.DataFrame(data, index=index)
    return CandleSchema.validate(df)


@pytest.fixture
def empty_candle_df() -> DataFrame[CandleSchema]:
    """빈 캔들 DataFrame을 반환합니다."""
    data = {
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": [],
        "value": [],
    }
    df = pd.DataFrame(data, index=pd.DatetimeIndex([]))
    return CandleSchema.validate(df)


@pytest.fixture
def candle_df_with_nat() -> DataFrame[CandleSchema]:
    """NaT 값을 포함한 캔들 DataFrame을 반환합니다."""
    data = {
        "open": [100.0, 200.0, 300.0],
        "high": [110.0, 210.0, 310.0],
        "low": [90.0, 190.0, 290.0],
        "close": [105.0, 205.0, 305.0],
        "volume": [1000.0, 2000.0, 3000.0],
        "value": [105000.0, 410000.0, 915000.0],
    }
    index = pd.DatetimeIndex(
        [
            datetime(2024, 1, 1, 9, 0, 0, tzinfo=pytz.UTC),
            pd.NaT,  # NaT 값
            datetime(2024, 1, 1, 11, 0, 0, tzinfo=pytz.UTC),
        ]
    )
    df = pd.DataFrame(data, index=index)
    return CandleSchema.validate(df)


def test_to_candle_models_with_valid_data(
        upbit_adapter: UpbitCandleAdapter, sample_candle_df: DataFrame[CandleSchema]
) -> None:
    """유효한 DataFrame을 CandleMinute1 또는 CandleDaily로 정상 변환하는지 테스트합니다."""
    # Given
    ticker = "KRW-BTC"
    interval = UpbitInterval.MINUTE_1  # 1분봉 사용 (지원되는 interval)

    # When
    result = upbit_adapter.to_candle_models(sample_candle_df, ticker, interval)

    # Then
    assert len(result) == 3
    assert all(isinstance(candle, (CandleMinute1, CandleDaily)) for candle in result)

    # 첫 번째 캔들 데이터 검증
    first_candle = result[0]
    assert first_candle.ticker == ticker
    assert first_candle.open == 100.0
    assert first_candle.high == 110.0
    assert first_candle.low == 90.0
    assert first_candle.close == 105.0
    assert first_candle.volume == 1000.0

    # UTC timezone-aware datetime으로 저장됨
    expected_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=pytz.UTC)
    assert first_candle.timestamp == expected_time
    assert first_candle.timestamp.tzinfo is not None


def test_to_candle_models_with_empty_dataframe(
        upbit_adapter: UpbitCandleAdapter, empty_candle_df: DataFrame[CandleSchema]
) -> None:
    """빈 DataFrame을 빈 리스트로 변환하는지 테스트합니다."""
    # Given
    ticker = "KRW-BTC"
    interval = UpbitInterval.MINUTE_1

    # When
    result = upbit_adapter.to_candle_models(empty_candle_df, ticker, interval)

    # Then
    assert result == []


def test_to_candle_models_with_invalid_interval_type(
        upbit_adapter: UpbitCandleAdapter, sample_candle_df: DataFrame[CandleSchema]
) -> None:
    """잘못된 interval 타입을 전달하면 TypeError가 발생하는지 테스트합니다."""
    # Given
    ticker = "KRW-BTC"
    invalid_interval = "invalid_interval"  # 문자열은 UpbitInterval이 아님

    # When & Then
    with pytest.raises(TypeError, match="Expected UpbitCandleInterval"):
        upbit_adapter.to_candle_models(sample_candle_df, ticker, invalid_interval)


def test_to_candle_models_skips_nat_values(
        upbit_adapter: UpbitCandleAdapter, candle_df_with_nat: DataFrame[CandleSchema]
) -> None:
    """NaT 값을 포함한 DataFrame에서 NaT 행을 스킵하고 유효한 행만 변환하는지 테스트합니다."""
    # Given
    ticker = "KRW-BTC"
    interval = UpbitInterval.DAY

    # When
    result = upbit_adapter.to_candle_models(candle_df_with_nat, ticker, interval)

    # Then
    # NaT 행은 스킵되므로 2개만 반환되어야 함
    assert len(result) == 2

    # 첫 번째와 세 번째 행만 변환됨 (UTC timezone-aware)
    assert result[0].timestamp == datetime(2024, 1, 1, 9, 0, 0, tzinfo=pytz.UTC)
    assert result[1].timestamp == datetime(2024, 1, 1, 11, 0, 0, tzinfo=pytz.UTC)


def test_timezone_preserved_as_utc_aware(
        upbit_adapter: UpbitCandleAdapter, sample_candle_df: DataFrame[CandleSchema]
) -> None:
    """UTC timezone-aware timestamp가 그대로 유지되는지 테스트합니다."""
    # Given
    ticker = "KRW-BTC"
    interval = UpbitInterval.MINUTE_1

    # When
    result = upbit_adapter.to_candle_models(sample_candle_df, ticker, interval)

    # Then
    # UTC aware → UTC aware (변환 없이 그대로 유지)
    # UTC 2024-01-01 09:00:00+00:00 (aware) → UTC 2024-01-01 09:00:00+00:00 (aware)
    # UTC 2024-01-01 10:00:00+00:00 (aware) → UTC 2024-01-01 10:00:00+00:00 (aware)
    # UTC 2024-01-01 11:00:00+00:00 (aware) → UTC 2024-01-01 11:00:00+00:00 (aware)

    expected_times = [
        datetime(2024, 1, 1, 9, 0, 0, tzinfo=pytz.UTC),
        datetime(2024, 1, 1, 10, 0, 0, tzinfo=pytz.UTC),
        datetime(2024, 1, 1, 11, 0, 0, tzinfo=pytz.UTC),
    ]

    for i, candle in enumerate(result):
        assert candle.timestamp == expected_times[i]
        assert candle.timestamp.tzinfo is not None  # timezone-aware datetime 확인


@pytest.mark.parametrize(
    "upbit_interval, expected_model_type",
    [
        (UpbitInterval.MINUTE_1, CandleMinute1),
        (UpbitInterval.DAY, CandleDaily),
    ],
)
def test_interval_conversion(
        upbit_adapter: UpbitCandleAdapter,
        sample_candle_df: DataFrame[CandleSchema],
        upbit_interval: UpbitInterval,
        expected_model_type: type,
) -> None:
    """UpbitInterval이 적절한 모델 타입(CandleMinute1 또는 CandleDaily)으로 변환되는지 테스트합니다."""
    # Given
    ticker = "KRW-BTC"

    # When
    result = upbit_adapter.to_candle_models(sample_candle_df, ticker, upbit_interval)

    # Then
    assert all(isinstance(candle, expected_model_type) for candle in result)
