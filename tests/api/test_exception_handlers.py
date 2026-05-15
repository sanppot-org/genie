"""전역 예외 핸들러 테스트."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.exception_handlers import handle_unhandled_exception


def test_unhandled_exception_returns_500_with_error_type_and_message() -> None:
    """미처리 예외는 500 + {error: type, message: str} JSON으로 반환된다."""
    app = FastAPI()
    app.add_exception_handler(Exception, handle_unhandled_exception)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("폭발")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"error": "RuntimeError", "message": "폭발"}
