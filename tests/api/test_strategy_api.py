"""VolatilityStrategy API 테스트"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.strategy.cache.cache_models import VolatilityStrategyCacheData


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient 픽스처"""
    return TestClient(app)


@pytest.fixture
def mock_cache_full_position() -> VolatilityStrategyCacheData:
    """전체 포지션이 있는 캐시 픽스처"""
    return VolatilityStrategyCacheData(
        execution_volume=0.5,
        last_run_date=date.today(),
        position_size=0.8,
        threshold=95_000_000.0,
    )


@pytest.fixture
def mock_cache_partial_position() -> VolatilityStrategyCacheData:
    """부분 포지션이 있는 캐시 픽스처"""
    return VolatilityStrategyCacheData(
        execution_volume=0.3,
        last_run_date=date.today(),
        position_size=0.8,
        threshold=95_000_000.0,
    )


def test_루트_엔드포인트(client: TestClient) -> None:
    """루트 엔드포인트는 성공 메시지를 반환한다"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Genie Trading Strategy API"}


def test_헬스체크_엔드포인트(client: TestClient) -> None:
    """헬스체크 엔드포인트는 ok 상태를 반환한다"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("src.api._create_volatility_strategy")
def test_매도_성공_전량_체결(
    mock_create_strategy: MagicMock,
    client: TestClient,
    mock_cache_full_position: VolatilityStrategyCacheData,
) -> None:
    """매도 요청 시 전량 체결되면 성공 응답을 반환한다"""
    # Given: VolatilityStrategy mock 설정
    mock_strategy = MagicMock()
    mock_strategy.manual_sell.return_value = {
        "success": True,
        "message": "매도가 완전히 체결되었습니다.",
        "executed_volume": 0.5,
        "remaining_volume": 0.0,
    }
    mock_create_strategy.return_value = mock_strategy

    # When: POST /api/strategy/sell 요청
    response = client.post("/api/strategy/sell", json={"ticker": "KRW-BTC"})

    # Then: 성공 응답
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "매도가 완전히 체결되었습니다."
    assert data["executed_volume"] == 0.5
    assert data["remaining_volume"] == 0.0


@patch("src.api._create_volatility_strategy")
def test_매도_성공_부분_체결(
    mock_create_strategy: MagicMock,
    client: TestClient,
    mock_cache_partial_position: VolatilityStrategyCacheData,
) -> None:
    """매도 요청 시 부분 체결되면 부분 체결 메시지를 반환한다"""
    # Given: VolatilityStrategy mock 설정
    mock_strategy = MagicMock()
    mock_strategy.manual_sell.return_value = {
        "success": True,
        "message": "매도가 부분 체결되었습니다.",
        "executed_volume": 0.2,
        "remaining_volume": 0.1,
    }
    mock_create_strategy.return_value = mock_strategy

    # When: POST /api/strategy/sell 요청
    response = client.post("/api/strategy/sell", json={"ticker": "KRW-BTC"})

    # Then: 부분 체결 응답
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "매도가 부분 체결되었습니다."
    assert data["executed_volume"] == 0.2
    assert data["remaining_volume"] == 0.1


@patch("src.api._create_volatility_strategy")
def test_매도_실패_캐시_없음(
    mock_create_strategy: MagicMock,
    client: TestClient,
) -> None:
    """캐시가 없으면 실패 응답을 반환한다"""
    # Given: VolatilityStrategy mock 설정 (캐시 없음)
    mock_strategy = MagicMock()
    mock_strategy.manual_sell.return_value = {
        "success": False,
        "message": "캐시가 존재하지 않습니다.",
        "executed_volume": None,
        "remaining_volume": None,
    }
    mock_create_strategy.return_value = mock_strategy

    # When: POST /api/strategy/sell 요청
    response = client.post("/api/strategy/sell", json={"ticker": "KRW-BTC"})

    # Then: 실패 응답
    assert response.status_code == 200  # HTTP 200이지만 success=False
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "캐시가 존재하지 않습니다."
    assert data["executed_volume"] is None
    assert data["remaining_volume"] is None


@patch("src.api._create_volatility_strategy")
def test_매도_실패_포지션_없음(
    mock_create_strategy: MagicMock,
    client: TestClient,
) -> None:
    """오늘 매수한 포지션이 없으면 실패 응답을 반환한다"""
    # Given: VolatilityStrategy mock 설정 (포지션 없음)
    mock_strategy = MagicMock()
    mock_strategy.manual_sell.return_value = {
        "success": False,
        "message": "오늘 매수한 포지션이 없습니다.",
        "executed_volume": None,
        "remaining_volume": None,
    }
    mock_create_strategy.return_value = mock_strategy

    # When: POST /api/strategy/sell 요청
    response = client.post("/api/strategy/sell", json={"ticker": "KRW-BTC"})

    # Then: 실패 응답
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "오늘 매수한 포지션이 없습니다."


@patch("src.api._create_volatility_strategy")
def test_매도_실패_체결되지_않음(
    mock_create_strategy: MagicMock,
    client: TestClient,
) -> None:
    """매도 주문이 체결되지 않으면 실패 응답을 반환한다"""
    # Given: VolatilityStrategy mock 설정 (체결 실패)
    mock_strategy = MagicMock()
    mock_strategy.manual_sell.return_value = {
        "success": False,
        "message": "매도 주문이 체결되지 않았습니다.",
        "executed_volume": 0.0,
        "remaining_volume": 0.5,
    }
    mock_create_strategy.return_value = mock_strategy

    # When: POST /api/strategy/sell 요청
    response = client.post("/api/strategy/sell", json={"ticker": "KRW-BTC"})

    # Then: 실패 응답
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "매도 주문이 체결되지 않았습니다."
    assert data["executed_volume"] == 0.0
    assert data["remaining_volume"] == 0.5


def test_매도_실패_유효하지_않은_티커(client: TestClient) -> None:
    """유효하지 않은 ticker로 요청하면 400 에러를 반환한다"""
    # When: 유효하지 않은 ticker로 요청
    response = client.post("/api/strategy/sell", json={"ticker": "KRW-INVALID"})

    # Then: 400 에러
    assert response.status_code == 400
    assert "유효하지 않은 ticker" in response.json()["detail"]


def test_매도_요청_ticker_없이(client: TestClient) -> None:
    """ticker 없이 요청하면 기본 ticker를 사용한다"""
    # Given: _create_volatility_strategy mock
    with patch("src.api._create_volatility_strategy") as mock_create:
        mock_strategy = MagicMock()
        mock_strategy.manual_sell.return_value = {
            "success": True,
            "message": "매도가 완전히 체결되었습니다.",
            "executed_volume": 0.5,
            "remaining_volume": 0.0,
        }
        mock_create.return_value = mock_strategy

        # When: ticker 없이 요청
        response = client.post("/api/strategy/sell", json={})

        # Then: 성공 (기본 ticker 사용)
        assert response.status_code == 200
        # _create_volatility_strategy가 호출되었는지 확인
        mock_create.assert_called_once()
        # 첫 번째 인자가 기본 ticker인지 확인
        called_ticker = mock_create.call_args[0][0]
        assert called_ticker in ["KRW-BTC", "KRW-ETH", "KRW-XRP"]  # tasks_context의 tickers 중 하나
