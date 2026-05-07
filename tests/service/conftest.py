"""Pytest fixtures for service tests."""

from unittest.mock import MagicMock

import pytest

from src.adapters.adapter_factory import CandleAdapterFactory
from src.database.candle_repositories import CandleDailyRepository, CandleMinute1Repository
from src.service.candle_query_service import CandleQueryService
from src.service.candle_service import CandleService


@pytest.fixture
def adapter_factory() -> CandleAdapterFactory:
    """어댑터 팩토리 fixture"""
    return CandleAdapterFactory()


@pytest.fixture
def mock_query_service() -> MagicMock:
    """Mock CandleQueryService fixture"""
    return MagicMock(spec=CandleQueryService)


@pytest.fixture
def candle_service(
        minute1_repo: CandleMinute1Repository,
        daily_repo: CandleDailyRepository,
        adapter_factory: CandleAdapterFactory,
        mock_query_service: MagicMock,
) -> CandleService:
    """CandleService fixture"""
    return CandleService(minute1_repo, daily_repo, adapter_factory, mock_query_service)
