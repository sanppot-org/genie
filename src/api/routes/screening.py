"""KR 주식 스크리닝 API — 5개 지표 점수 합산 랭킹."""
# ruff: noqa: B008

from dataclasses import asdict
from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.api.schemas import (
    GenieResponse,
    ScreeningResponse,
    ScreeningRowResponse,
    ScreeningScoreBreakdown,
)
from src.container import ApplicationContainer
from src.service.screening_service import ScreeningResult, ScreeningService

router = APIRouter(tags=["screening"])


@router.get("/screening/kr-stock", response_model=GenieResponse[ScreeningResponse])
@inject
def get_kr_stock_screening(
        date_str: str | None = Query(default=None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        service: ScreeningService = Depends(Provide[ApplicationContainer.screening_service]),
) -> GenieResponse[ScreeningResponse]:
    """전체 KR_STOCK을 5개 지표 점수 합산해 total_score DESC, ticker ASC로 정렬.

    `date` 미지정 시 `stock_fundamentals` 최신 일자 사용. 데이터 없으면 빈 결과.
    """
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
    result = service.score_kr_stocks(target_date=target_date, limit=limit, offset=offset)
    return GenieResponse(data=_to_response(result))


def _to_response(result: ScreeningResult) -> ScreeningResponse:
    return ScreeningResponse(
        target_date=result.target_date,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        rows=[
            ScreeningRowResponse(
                ticker=r.ticker,
                name=r.name,
                per=r.per,
                pbr=r.pbr,
                dividend_yield=r.dividend_yield,
                quarterly_dividend=r.quarterly_dividend,
                consecutive_increase_years=r.consecutive_increase_years,
                scores=ScreeningScoreBreakdown(**asdict(r.scores)),
                total_score=r.total_score,
            )
            for r in result.rows
        ],
    )
