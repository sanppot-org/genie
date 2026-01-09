"""Candle API 테스트"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import app, container
from src.service.candle_service import CandleService, CollectMode


@pytest.fixture
def mock_candle_service() -> MagicMock:
    """Mock CandleService 픽스처"""
    return MagicMock(spec=CandleService)


@pytest.fixture
def client_with_mock(mock_candle_service: MagicMock) -> TestClient:
    """DI override가 적용된 TestClient 픽스처"""
    # app.py에서 생성된 container 인스턴스의 provider override
    container.candle_service.override(mock_candle_service)
    yield TestClient(app)
    # Reset override after test
    container.candle_service.reset_override()


def test_수집_성공_기본_파라미터(
        client_with_mock: TestClient,
        mock_candle_service: MagicMock,
) -> None:
    """기본 파라미터로 1분봉 수집 요청 시 성공 응답을 반환한다"""
    # Given: CandleService mock 설정
    mock_candle_service.collect_minute1_candles.return_value = 1500

    # When: POST /api/candles/collect 요청
    response = client_with_mock.post(
        "/api/candles/collect",
        json={"ticker": "KRW-BTC"},
    )

    # Then: 성공 응답
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total_saved"] == 1500
    assert data["data"]["ticker"] == "KRW-BTC"
    assert data["data"]["mode"] == "INCREMENTAL"

    # 서비스 메서드 호출 검증
    mock_candle_service.collect_minute1_candles.assert_called_once()
    call_kwargs = mock_candle_service.collect_minute1_candles.call_args.kwargs
    assert call_kwargs["ticker"] == "KRW-BTC"
    assert call_kwargs["mode"] == CollectMode.INCREMENTAL
    assert call_kwargs["batch_size"] == 1000
    assert call_kwargs["to"] is None


def test_수집_성공_전체_파라미터(
        client_with_mock: TestClient,
        mock_candle_service: MagicMock,
) -> None:
    """모든 파라미터를 지정하여 1분봉 수집 요청 시 성공 응답을 반환한다"""
    # Given: CandleService mock 설정
    mock_candle_service.collect_minute1_candles.return_value = 500

    # When: POST /api/candles/collect 요청 (모든 파라미터)
    response = client_with_mock.post(
        "/api/candles/collect",
        json={
            "ticker": "KRW-ETH",
            "to": "2024-01-15T10:30:00",
            "batch_size": 500,
            "mode": "FULL",
        },
    )

    # Then: 성공 응답
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total_saved"] == 500
    assert data["data"]["ticker"] == "KRW-ETH"
    assert data["data"]["mode"] == "FULL"

    # 서비스 메서드 호출 검증
    call_kwargs = mock_candle_service.collect_minute1_candles.call_args.kwargs
    assert call_kwargs["mode"] == CollectMode.FULL
    assert call_kwargs["batch_size"] == 500


def test_수집_성공_backfill_모드(
        client_with_mock: TestClient,
        mock_candle_service: MagicMock,
) -> None:
    """BACKFILL 모드로 1분봉 수집 요청 시 성공 응답을 반환한다"""
    # Given: CandleService mock 설정
    mock_candle_service.collect_minute1_candles.return_value = 2000

    # When: POST /api/candles/collect 요청 (BACKFILL 모드)
    response = client_with_mock.post(
        "/api/candles/collect",
        json={
            "ticker": "KRW-XRP",
            "mode": "BACKFILL",
        },
    )

    # Then: 성공 응답
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total_saved"] == 2000
    assert data["data"]["ticker"] == "KRW-XRP"
    assert data["data"]["mode"] == "BACKFILL"

    # 서비스 메서드 호출 검증
    call_kwargs = mock_candle_service.collect_minute1_candles.call_args.kwargs
    assert call_kwargs["mode"] == CollectMode.BACKFILL


def test_수집_실패_잘못된_mode() -> None:
    """유효하지 않은 mode로 요청하면 422 에러를 반환한다"""
    # Given
    client = TestClient(app)

    # When: POST /api/candles/collect 요청 (잘못된 mode)
    response = client.post(
        "/api/candles/collect",
        json={
            "ticker": "KRW-BTC",
            "mode": "INVALID_MODE",
        },
    )

    # Then: 422 에러 (Pydantic validation error)
    assert response.status_code == 422


def test_수집_실패_ticker_누락() -> None:
    """ticker가 누락되면 422 에러를 반환한다"""
    # Given: 별도의 mock 없이 TestClient 사용 (validation 테스트)
    client = TestClient(app)

    # When: POST /api/candles/collect 요청 (ticker 누락)
    response = client.post(
        "/api/candles/collect",
        json={"batch_size": 1000},
    )

    # Then: 422 에러
    assert response.status_code == 422


def test_수집_실패_서비스_예외(
        mock_candle_service: MagicMock,
) -> None:
    """서비스에서 예외 발생 시 500 에러를 반환한다"""
    # Given: CandleService가 예외를 발생시킴
    mock_candle_service.collect_minute1_candles.side_effect = ValueError(
        "batch_size는 0보다 커야 합니다"
    )
    container.candle_service.override(mock_candle_service)
    client = TestClient(app, raise_server_exceptions=False)

    # When: POST /api/candles/collect 요청
    response = client.post(
        "/api/candles/collect",
        json={
            "ticker": "KRW-BTC",
            "batch_size": 0,
        },
    )

    # Then: 500 에러
    assert response.status_code == 500
    container.candle_service.reset_override()
