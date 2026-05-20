"""KR 주식 스크리닝 API — 5개 지표 점수 합산 랭킹."""
# ruff: noqa: B008

from dataclasses import asdict
from datetime import datetime
from typing import Literal

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.api.schemas import (
    GenieResponse,
    ScreeningResponse,
    ScreeningRowResponse,
    ScreeningScoreBreakdown,
)
from src.container import ApplicationContainer
from src.service.screening_service import ScreeningFilters, ScreeningResult, ScreeningService

router = APIRouter(tags=["screening"])

ScreeningSortBy = Literal[
    "total_score", "per", "pbr", "dividend_yield",
    "quarterly_dividend", "consecutive_years", "ticker",
]
ScreeningSortOrder = Literal["asc", "desc"]


@router.get("/screening/kr-stock", response_model=GenieResponse[ScreeningResponse])
@inject
def get_kr_stock_screening(
        date_str: str | None = Query(default=None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        sort_by: ScreeningSortBy = Query(default="total_score"),
        order: ScreeningSortOrder = Query(default="desc"),
        per_min: float | None = Query(default=None, ge=0),
        per_max: float | None = Query(default=None, ge=0),
        pbr_min: float | None = Query(default=None, ge=0),
        pbr_max: float | None = Query(default=None, ge=0),
        dividend_yield_min: float | None = Query(default=None, ge=0),
        q: str | None = Query(default=None, max_length=50),
        service: ScreeningService = Depends(Provide[ApplicationContainer.screening_service]),
) -> GenieResponse[ScreeningResponse]:
    """전체 KR_STOCK을 5개 지표 점수 합산해 sort_by/order 기준으로 정렬.

    기본은 total_score DESC, ticker ASC. NULL 값은 정렬 방향과 무관하게 항상 맨 뒤.
    `date` 미지정 시 `stock_fundamentals` 최신 일자 사용. 데이터 없으면 빈 결과.
    필터(`per_min`/`per_max`/`pbr_min`/`pbr_max`/`dividend_yield_min`) 활성 시
    해당 컬럼 NULL 종목은 자동 제외. `q`는 ticker / name substring 검색(대소문자 무시).
    """
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
    filters = ScreeningFilters(
        per_min=per_min, per_max=per_max,
        pbr_min=pbr_min, pbr_max=pbr_max,
        dividend_yield_min=dividend_yield_min,
        q=q,
    )
    result = service.score_kr_stocks(
        target_date=target_date, limit=limit, offset=offset,
        sort_by=sort_by, order=order, filters=filters,
    )
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
