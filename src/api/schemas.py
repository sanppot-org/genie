"""API 스키마 정의"""

from pydantic import BaseModel


class SellResponse(BaseModel):
    """매도 응답 모델"""

    success: bool
    message: str
    executed_volume: float | None = None
    remaining_volume: float | None = None
