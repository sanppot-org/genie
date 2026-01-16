"""Service layer exceptions."""
from enum import Enum

from starlette.responses import JSONResponse


class StatusCode(Enum):
    OK = 200
    BAD_REQUEST = 400
    NOT_FOUND = 404
    CONFLICT = 409


class ExceptionCode(Enum):
    NOT_FOUND = (StatusCode.NOT_FOUND, "엔티티를 찾을 수 없습니다. ID: {id}")
    ALREADY_EXISTS = (StatusCode.CONFLICT, "이미 존재합니다: {name}")

    def __init__(self, status_code: StatusCode, message: str) -> None:
        self.statusCode = status_code
        self.message = message


class GenieError(Exception):
    def __init__(self, code: ExceptionCode, **kwargs: int | str) -> None:
        self.code = code
        self.message = code.message.format(**kwargs)

    def to_json_response(self) -> JSONResponse:
        return JSONResponse(content=self.message, status_code=self.code.statusCode.value)

    @staticmethod
    def not_found(entity_id: int) -> "GenieError":
        return GenieError(code=ExceptionCode.NOT_FOUND, id=entity_id)

    @staticmethod
    def already_exists(name: str) -> "GenieError":
        return GenieError(code=ExceptionCode.ALREADY_EXISTS, name=name)
