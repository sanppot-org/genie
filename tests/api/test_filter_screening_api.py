"""POST /api/screening/filter API 테스트."""

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app import app, container
from src.service.rule_screener.service import (
    RuleScreeningResult,
    RuleScreeningRow,
    RuleScreeningService,
)


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock(spec=RuleScreeningService)


@pytest.fixture
def client(mock_service: MagicMock) -> Generator[TestClient, None, None]:
    container.rule_screening_service.override(mock_service)
    yield TestClient(app, raise_server_exceptions=False)
    container.rule_screening_service.reset_override()


def test_post_filter_returns_rows(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.screen.return_value = RuleScreeningResult(
        total=1, limit=50, offset=0,
        rows=[RuleScreeningRow(ticker="A00001", name="우량주", total_score=42,
                               metrics={"bsop_prti": {"count": 5.0, "window": 5}, "per": 12.0})],
    )
    body = {
        "conditions": [
            {"metric": "bsop_prti", "op": "count", "window": 5,
             "predicate": {"cmp": "gt", "value": 0}, "min_count": 4},
            {"metric": "per", "op": "cmp", "cmp": "lt", "value": 15},
        ],
        "sort_by": "total_score", "order": "desc", "limit": 50, "offset": 0,
    }
    resp = client.post("/api/screening/filter", json=body)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["rows"][0]["ticker"] == "A00001"
    assert data["rows"][0]["metrics"]["bsop_prti"]["count"] == 5.0


def test_post_filter_invalid_metric_returns_400(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.screen.side_effect = ValueError("알 수 없는 지표: nope")
    body = {"conditions": [{"metric": "nope", "op": "cmp", "cmp": "lt", "value": 1}]}
    resp = client.post("/api/screening/filter", json=body)

    assert resp.status_code == 400
    assert "알 수 없는 지표" in resp.json()["detail"]


def test_post_filter_empty_conditions_returns_422(client: TestClient) -> None:
    resp = client.post("/api/screening/filter", json={"conditions": []})
    assert resp.status_code == 422  # Pydantic min_length=1
