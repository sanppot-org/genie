import datetime as dt
import tempfile
from pathlib import Path

import pytest

from src.strategy.cache_manager import CacheManager
from src.strategy.cache_models import DataCache, StrategyCache
from src.strategy.data.models import HalfDayCandle, Recent20DaysHalfDayCandles


@pytest.fixture
def temp_cache_dir():
    """임시 캐시 디렉토리 생성"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_history():
    """테스트용 샘플 히스토리 데이터"""
    from src.strategy.data.models import Period

    # 20일간의 오전/오후 캔들 생성 (총 40개)
    candles = []
    base_date = dt.date(2023, 12, 14)  # 20일 전

    for day_offset in range(20):
        current_date = base_date + dt.timedelta(days=day_offset)

        # 오전 캔들
        morning = HalfDayCandle(
            date=current_date,
            period=Period.MORNING,
            open=100.0,
            high=110.0,
            low=95.0,
            close=105.0,
            volume=1000.0,
        )
        candles.append(morning)

        # 오후 캔들
        afternoon = HalfDayCandle(
            date=current_date,
            period=Period.AFTERNOON,
            open=105.0,
            high=115.0,
            low=100.0,
            close=110.0,
            volume=1200.0,
        )
        candles.append(afternoon)

    return Recent20DaysHalfDayCandles(candles=candles)


@pytest.fixture
def sample_data_cache(sample_history):
    """테스트용 DataCache"""
    today = dt.date(2024, 1, 2)

    return DataCache(
        ticker="KRW-BTC",
        last_update_date=today,
        history=sample_history,
    )


@pytest.fixture
def sample_strategy_cache():
    """테스트용 StrategyCache"""
    today = dt.date(2024, 1, 2)

    return StrategyCache(
        ticker="KRW-BTC",
        last_run_date=today,
        volatility_position_size=0.5,
        volatility_threshold=105.0,
        volatility_execution_volume=0.0,
        morning_afternoon_execution_volume=0.0,
    )


class TestCacheManager:
    def test_cache_file_path_with_suffix(self, temp_cache_dir):
        """file_suffix가 있을 때 캐시 파일 경로가 올바르게 생성되는지 검증"""
        manager = CacheManager(cache_dir=temp_cache_dir, file_suffix="strategy")

        expected_path = Path(temp_cache_dir) / "KRW-BTC_strategy_cache.json"
        assert manager.get_cache_path("KRW-BTC") == expected_path

    def test_cache_file_path_without_suffix(self, temp_cache_dir):
        """file_suffix가 없을 때 캐시 파일 경로가 올바르게 생성되는지 검증"""
        manager = CacheManager(cache_dir=temp_cache_dir)

        expected_path = Path(temp_cache_dir) / "KRW-BTC_cache.json"
        assert manager.get_cache_path("KRW-BTC") == expected_path

    def test_save_and_load_strategy_cache(self, temp_cache_dir, sample_strategy_cache):
        """StrategyCache 저장 후 로드가 정상 동작하는지 검증"""
        manager = CacheManager(cache_dir=temp_cache_dir, file_suffix="strategy")
        ticker = "KRW-BTC"

        # 저장
        manager.save_strategy_cache(ticker, sample_strategy_cache)

        # 로드
        loaded_cache = manager.load_strategy_cache(ticker)

        # 검증
        assert loaded_cache is not None
        assert loaded_cache.last_run_date == sample_strategy_cache.last_run_date
        assert loaded_cache.volatility_position_size == sample_strategy_cache.volatility_position_size
        assert loaded_cache.volatility_threshold == sample_strategy_cache.volatility_threshold

    def test_save_and_load_data_cache(self, temp_cache_dir, sample_data_cache):
        """DataCache 저장 후 로드가 정상 동작하는지 검증"""
        manager = CacheManager(cache_dir=temp_cache_dir, file_suffix="data")
        ticker = "KRW-BTC"

        # 저장
        manager.save_data_cache(ticker, sample_data_cache)

        # 로드
        loaded_cache = manager.load_data_cache(ticker)

        # 검증
        assert loaded_cache is not None
        assert loaded_cache.last_update_date == sample_data_cache.last_update_date
        assert loaded_cache.ticker == sample_data_cache.ticker
        assert len(loaded_cache.history.candles) == 40

    def test_load_nonexistent_cache(self, temp_cache_dir):
        """존재하지 않는 캐시 로드 시 None 반환"""
        manager = CacheManager(cache_dir=temp_cache_dir, file_suffix="strategy")

        loaded_cache = manager.load_strategy_cache("NONEXISTENT")

        assert loaded_cache is None

    def test_cache_directory_auto_creation(self, temp_cache_dir, sample_strategy_cache):
        """캐시 디렉토리가 자동으로 생성되는지 검증"""
        # 존재하지 않는 하위 디렉토리 경로
        cache_path = Path(temp_cache_dir) / "subdir" / "cache"
        manager = CacheManager(cache_dir=str(cache_path), file_suffix="strategy")

        # 저장 시 디렉토리가 자동 생성되어야 함
        manager.save_strategy_cache("KRW-BTC", sample_strategy_cache)

        # 디렉토리 생성 확인
        assert cache_path.exists()
        assert cache_path.is_dir()

    def test_overwrite_existing_cache(self, temp_cache_dir, sample_strategy_cache):
        """기존 캐시를 덮어쓰는지 검증"""
        manager = CacheManager(cache_dir=temp_cache_dir, file_suffix="strategy")
        ticker = "KRW-BTC"

        # 첫 번째 저장
        manager.save_strategy_cache(ticker, sample_strategy_cache)

        # 캐시 수정
        modified_cache = sample_strategy_cache.model_copy()
        modified_cache.volatility_position_size = 0.8

        # 덮어쓰기
        manager.save_strategy_cache(ticker, modified_cache)

        # 로드 후 검증
        loaded_cache = manager.load_strategy_cache(ticker)
        assert loaded_cache.volatility_position_size == 0.8
