"""AllocationBalanceProvider 테스트"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.allocation_manager import AllocatedAmount, AllocatedBalanceProvider
from src.constants import KST


@pytest.fixture
def temp_state_file(tmp_path: Path) -> Path:
    """임시 상태 파일 경로"""
    return tmp_path / "test_allocation.json"


@pytest.fixture
def mock_upbit_api() -> Mock:
    """Mock UpbitAPI"""
    mock = Mock()
    mock.get_available_amount.return_value = 50000.0
    return mock


class TestAllocatedAmount:
    """AllocatedAmount 모델 테스트"""

    def test_default_datetime(self) -> None:
        """기본 datetime은 현재 시각"""
        amount = AllocatedAmount(allocated_balance_per_ticker=10000.0)
        assert amount.last_allocation_datetime.date() == datetime.now(KST).date()

    def test_custom_datetime(self) -> None:
        """커스텀 datetime 설정"""
        custom_dt = datetime(2024, 1, 15, 14, 30, tzinfo=KST)
        amount = AllocatedAmount(
            allocated_balance_per_ticker=10000.0,
            last_allocation_datetime=custom_dt
        )
        assert amount.last_allocation_datetime == custom_dt


class TestAllocatedBalanceProvider:
    """AllocatedBalanceProvider 클래스 테스트"""

    def test_no_cache_allocates_new(
            self, temp_state_file: Path, mock_upbit_api: Mock
    ) -> None:
        """캐시가 없으면 새로 할당"""
        provider = AllocatedBalanceProvider(state_file_path=temp_state_file, allocation_hour=23)
        provider.upbit_api = mock_upbit_api

        result = provider.get_allocated_amount()

        assert result == 50000.0
        mock_upbit_api.get_available_amount.assert_called_once()
        assert temp_state_file.exists()

    def test_same_day_before_allocation_hour_no_update(
            self, temp_state_file: Path, mock_upbit_api: Mock
    ) -> None:
        """같은 날, allocation_hour 이전에 갱신했고 현재도 이전이면 갱신 안 함"""
        # 15시에 캐시 생성
        earlier_time = datetime.now(KST).replace(hour=15, minute=0, second=0, microsecond=0)
        state = AllocatedAmount(
            allocated_balance_per_ticker=30000.0,
            last_allocation_datetime=earlier_time
        )
        with open(temp_state_file, "w") as f:
            json.dump(state.model_dump(mode="json"), f)

        provider = AllocatedBalanceProvider(state_file_path=temp_state_file, allocation_hour=23)
        provider.upbit_api = mock_upbit_api

        # 현재 시각을 18시로 설정
        with patch('src.allocation_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now(KST).replace(hour=18, minute=0)
            result = provider.get_allocated_amount()

        assert result == 30000.0  # 기존 값 반환
        mock_upbit_api.get_available_amount.assert_not_called()

    def test_same_day_after_allocation_hour_updates(
            self, temp_state_file: Path, mock_upbit_api: Mock
    ) -> None:
        """같은 날, 15시에 캐시 생성 → 23시에 갱신됨"""
        # 15시에 캐시 생성
        earlier_time = datetime.now(KST).replace(hour=15, minute=0, second=0, microsecond=0)
        state = AllocatedAmount(
            allocated_balance_per_ticker=30000.0,
            last_allocation_datetime=earlier_time
        )
        with open(temp_state_file, "w") as f:
            json.dump(state.model_dump(mode="json"), f)

        provider = AllocatedBalanceProvider(state_file_path=temp_state_file, allocation_hour=23)
        provider.upbit_api = mock_upbit_api

        # 현재 시각을 23시로 설정
        with patch('src.allocation_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now(KST).replace(hour=23, minute=0)
            result = provider.get_allocated_amount()

        assert result == 50000.0  # 새로 할당된 값
        mock_upbit_api.get_available_amount.assert_called_once()

    def test_same_day_already_allocated_no_update(
            self, temp_state_file: Path, mock_upbit_api: Mock
    ) -> None:
        """같은 날, 이미 23시 이후에 갱신했으면 다시 갱신 안 함"""
        # 23시에 캐시 생성
        allocated_time = datetime.now(KST).replace(hour=23, minute=0, second=0, microsecond=0)
        state = AllocatedAmount(
            allocated_balance_per_ticker=40000.0,
            last_allocation_datetime=allocated_time
        )
        with open(temp_state_file, "w") as f:
            json.dump(state.model_dump(mode="json"), f)

        provider = AllocatedBalanceProvider(state_file_path=temp_state_file, allocation_hour=23)
        provider.upbit_api = mock_upbit_api

        # 현재 시각을 23시 30분으로 설정
        with patch('src.allocation_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now(KST).replace(hour=23, minute=30)
            result = provider.get_allocated_amount()

        assert result == 40000.0  # 기존 값 반환
        mock_upbit_api.get_available_amount.assert_not_called()

    def test_new_day_before_allocation_hour_no_update(
            self, temp_state_file: Path, mock_upbit_api: Mock
    ) -> None:
        """날짜가 바뀌었지만 현재 시각이 allocation_hour 이전이면 갱신 안 함"""
        # 어제 캐시 생성
        yesterday = datetime.now(KST) - timedelta(days=1)
        state = AllocatedAmount(
            allocated_balance_per_ticker=35000.0,
            last_allocation_datetime=yesterday
        )
        with open(temp_state_file, "w") as f:
            json.dump(state.model_dump(mode="json"), f)

        provider = AllocatedBalanceProvider(state_file_path=temp_state_file, allocation_hour=23)
        provider.upbit_api = mock_upbit_api

        # 현재 시각을 오늘 15시로 설정
        with patch('src.allocation_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now(KST).replace(hour=15, minute=0)
            result = provider.get_allocated_amount()

        assert result == 35000.0  # 기존 값 반환
        mock_upbit_api.get_available_amount.assert_not_called()

    def test_new_day_after_allocation_hour_updates(
            self, temp_state_file: Path, mock_upbit_api: Mock
    ) -> None:
        """날짜가 바뀌고 현재 시각이 allocation_hour 이후면 갱신"""
        # 어제 캐시 생성
        yesterday = datetime.now(KST) - timedelta(days=1)
        state = AllocatedAmount(
            allocated_balance_per_ticker=35000.0,
            last_allocation_datetime=yesterday
        )
        with open(temp_state_file, "w") as f:
            json.dump(state.model_dump(mode="json"), f)

        provider = AllocatedBalanceProvider(state_file_path=temp_state_file, allocation_hour=23)
        provider.upbit_api = mock_upbit_api

        # 현재 시각을 오늘 23시로 설정
        with patch('src.allocation_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now(KST).replace(hour=23, minute=0)
            result = provider.get_allocated_amount()

        assert result == 50000.0  # 새로 할당된 값
        mock_upbit_api.get_available_amount.assert_called_once()
