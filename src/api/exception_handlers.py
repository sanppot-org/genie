"""전역 예외 핸들러."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from src.service import GenieError

logger = logging.getLogger(__name__)


async def handle_genie_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, GenieError)
    return exc.to_json_response()


async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """미처리 예외 — 500 + type/message JSON. 상세 traceback은 서버 로그에만 남김."""
    logger.exception("Unhandled exception at %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
        },
    )
