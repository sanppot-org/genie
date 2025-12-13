"""헬스체크 엔드포인트"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    """루트 엔드포인트"""
    return {"message": "Genie Trading Strategy API"}


@router.get("/health")
def health() -> dict[str, str]:
    """헬스체크 엔드포인트"""
    return {"status": "ok"}
