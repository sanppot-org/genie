"""GET /api/screening/kr-stock API 테스트."""

from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app import app, container
from src.service.screening_service import (
    ScoreBreakdown,
    ScreeningFilters,
    ScreeningResult,
    ScreeningRow,
    ScreeningService,
)


@pytest.fixture
def mock_screening_service() -> MagicMock:
    return MagicMock(spec=ScreeningService)


@pytest.fixture
def client(mock_screening_service: MagicMock) -> Generator[TestClient, None, None]:
    container.screening_service.override(mock_screening_service)
    yield TestClient(app, raise_server_exceptions=False)
    container.screening_service.reset_override()


def _row(ticker: str, total: int = 30) -> ScreeningRow:
    return ScreeningRow(
        ticker=ticker, name=f"{ticker}_name",
        per=5.0, pbr=0.5, dividend_yield=4.0,
        quarterly_dividend=True, consecutive_increase_years=4,
        scores=ScoreBreakdown(
            per=15, pbr=4, dividend_yield=5,
            quarterly_dividend=5, consecutive_increase_years=3,
        ),
        total_score=total,
    )


class TestScreeningAPI:
    def test_returns_ranked_rows(
            self, client: TestClient, mock_screening_service: MagicMock,
    ) -> None:
        """기본 호출 → 200 + 응답 형태 검증."""
        mock_screening_service.score_kr_stocks.return_value = ScreeningResult(
            target_date=date(2026, 5, 15),
            total=2, limit=50, offset=0,
            rows=[_row("A0001", total=45), _row("B0002", total=30)],
        )

        response = client.get("/api/screening/kr-stock")

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["target_date"] == "2026-05-15"
        assert body["total"] == 2
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert [r["ticker"] for r in body["rows"]] == ["A0001", "B0002"]
        assert body["rows"][0]["total_score"] == 45
        assert body["rows"][0]["scores"]["per"] == 15
        assert body["rows"][0]["quarterly_dividend"] is True

        mock_screening_service.score_kr_stocks.assert_called_once_with(
            target_date=None, limit=50, offset=0,
            sort_by="total_score", order="desc",
            filters=ScreeningFilters(),
        )

    def test_query_params_propagate(
            self, client: TestClient, mock_screening_service: MagicMock,
    ) -> None:
        """date/limit/offset/sort_by/order 파라미터가 그대로 service에 전달."""
        mock_screening_service.score_kr_stocks.return_value = ScreeningResult(
            target_date=date(2026, 4, 30), total=100, limit=10, offset=20, rows=[],
        )

        response = client.get(
            "/api/screening/kr-stock?date=2026-04-30&limit=10&offset=20"
            "&sort_by=per&order=asc",
        )

        assert response.status_code == 200
        mock_screening_service.score_kr_stocks.assert_called_once_with(
            target_date=date(2026, 4, 30), limit=10, offset=20,
            sort_by="per", order="asc",
            filters=ScreeningFilters(),
        )

    def test_filter_query_params_propagate(
            self, client: TestClient, mock_screening_service: MagicMock,
    ) -> None:
        """필터 Query가 ScreeningFilters로 묶여 service에 전달."""
        mock_screening_service.score_kr_stocks.return_value = ScreeningResult(
            target_date=date(2026, 5, 15), total=0, limit=50, offset=0, rows=[],
        )

        response = client.get(
            "/api/screening/kr-stock"
            "?per_min=2&per_max=5&pbr_min=0.3&pbr_max=1.0&dividend_yield_min=4",
        )

        assert response.status_code == 200
        mock_screening_service.score_kr_stocks.assert_called_once_with(
            target_date=None, limit=50, offset=0,
            sort_by="total_score", order="desc",
            filters=ScreeningFilters(
                per_min=2.0, per_max=5.0,
                pbr_min=0.3, pbr_max=1.0,
                dividend_yield_min=4.0,
            ),
        )

    def test_negative_filter_422(self, client: TestClient) -> None:
        """음수 필터는 ge=0 위반 → 422."""
        response = client.get("/api/screening/kr-stock?per_min=-1")
        assert response.status_code == 422

    def test_invalid_sort_by_422(self, client: TestClient) -> None:
        """sort_by가 enum 밖이면 422."""
        response = client.get("/api/screening/kr-stock?sort_by=foo")
        assert response.status_code == 422

    def test_invalid_order_422(self, client: TestClient) -> None:
        """order가 asc/desc 외 값이면 422."""
        response = client.get("/api/screening/kr-stock?order=updown")
        assert response.status_code == 422

    def test_invalid_date_format_422(self, client: TestClient) -> None:
        """date 패턴 불일치 시 422."""
        response = client.get("/api/screening/kr-stock?date=20260430")
        assert response.status_code == 422

    def test_limit_out_of_range_422(self, client: TestClient) -> None:
        """limit > 500 → 422."""
        response = client.get("/api/screening/kr-stock?limit=1000")
        assert response.status_code == 422

    def test_negative_offset_422(self, client: TestClient) -> None:
        """offset < 0 → 422."""
        response = client.get("/api/screening/kr-stock?offset=-1")
        assert response.status_code == 422

    def test_empty_result(
            self, client: TestClient, mock_screening_service: MagicMock,
    ) -> None:
        """데이터 없을 때 target_date=null + rows=[] + 200."""
        mock_screening_service.score_kr_stocks.return_value = ScreeningResult(
            target_date=None, total=0, limit=50, offset=0, rows=[],
        )

        response = client.get("/api/screening/kr-stock")

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["target_date"] is None
        assert body["total"] == 0
        assert body["rows"] == []
