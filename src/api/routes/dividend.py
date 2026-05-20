"""배당 이력 조회 API."""
# ruff: noqa: B008

from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.api.schemas import (
    DividendPoint,
    DividendSeriesResponse,
    GenieResponse,
)
from src.container import ApplicationContainer
from src.service.dividend_service import DividendService

router = APIRouter(tags=["dividends"])


@router.get("/dividends", response_model=GenieResponse[DividendSeriesResponse])
@inject
def get_dividends(
        ticker: str = Query(min_length=1, max_length=20, description="ticker 코드"),
        from_: str | None = Query(default=None, alias="from", pattern=r"^\d{8}$"),
        to: str | None = Query(default=None, pattern=r"^\d{8}$"),
        service: DividendService = Depends(Provide[ApplicationContainer.dividend_service]),
) -> GenieResponse[DividendSeriesResponse]:
    """종목별 배당 지급 이력 (record_date 오름차순). 종목 미발견 시 404."""
    from_date = datetime.strptime(from_, "%Y%m%d").date() if from_ else None
    to_date = datetime.strptime(to, "%Y%m%d").date() if to else None
    t, rows = service.get_history(ticker, from_date, to_date)
    return GenieResponse(
        data=DividendSeriesResponse(
            ticker=t.ticker,
            name=t.name,
            points=[DividendPoint.model_validate(r) for r in rows],
        )
    )
