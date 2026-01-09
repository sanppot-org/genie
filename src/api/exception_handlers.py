"""전역 예외 핸들러."""

from fastapi import Request
from fastapi.responses import JSONResponse

from src.service import GenieError


async def handle_exception(request: Request, exc: GenieError) -> JSONResponse:
    return exc.to_json_response()
