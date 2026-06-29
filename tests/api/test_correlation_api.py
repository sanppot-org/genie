"""Correlation API 테스트 — POST /api/correlation/run."""

from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app import app, container
from src.service.correlation_service import CorrelationOutput


@pytest.fixture
def mock_service() -> Generator[MagicMock, None, None]:
    """correlation_service DI provider를 mock으로 override."""
    mock = MagicMock()
    container.correlation_service.override(mock)
    yield mock
    container.correlation_service.reset_override()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _output(**kw: object) -> CorrelationOutput:
    defaults: dict[str, object] = {
        "tickers": ["AAA", "BBB"],
        "matrix": [[1.0, 0.5], [0.5, 1.0]],
        "observations": 100,
        "period_start": date(2024, 1, 2),
        "period_end": date(2024, 6, 28),
        "method": "pearson",
        "return_type": "returns",
        "dropped": [],
        "warnings": [],
    }
    defaults.update(kw)
    return CorrelationOutput(**defaults)  # type: ignore[arg-type]


def test_상관계산_성공(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.run.return_value = _output(dropped=["ZZZ"])

    resp = client.post("/api/correlation/run", json={"tickers": ["AAA", "BBB", "ZZZ"]})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tickers"] == ["AAA", "BBB"]
    assert data["matrix"] == [[1.0, 0.5], [0.5, 1.0]]
    assert data["observations"] == 100
    assert data["dropped"] == ["ZZZ"]
    # 서비스가 파싱된 date로 호출됐는지
    assert mock_service.run.call_args.kwargs["method"] == "pearson"


def test_티커_2개_미만은_422(client: TestClient, mock_service: MagicMock) -> None:
    resp = client.post("/api/correlation/run", json={"tickers": ["AAA"]})
    assert resp.status_code == 422


def test_잘못된_날짜_형식_400(client: TestClient, mock_service: MagicMock) -> None:
    resp = client.post("/api/correlation/run", json={"tickers": ["AAA", "BBB"], "start": "2024-01-01"})
    assert resp.status_code == 400
    assert "YYYYMMDD" in resp.json()["detail"]


def test_종료일_시작일_역전_400(client: TestClient, mock_service: MagicMock) -> None:
    resp = client.post(
        "/api/correlation/run",
        json={"tickers": ["AAA", "BBB"], "start": "20240601", "end": "20240101"},
    )
    assert resp.status_code == 400


def test_서비스_ValueError는_400(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.run.side_effect = ValueError("asset 미지원")
    resp = client.post("/api/correlation/run", json={"tickers": ["AAA", "BBB"]})
    assert resp.status_code == 400
    assert "asset" in resp.json()["detail"]
