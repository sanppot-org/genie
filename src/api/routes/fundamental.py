"""펀더멘털 동기화/조회 API 엔드포인트."""
# ruff: noqa: B008

from dataclasses import asdict
from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.api.schemas import (
    FundamentalPoint,
    FundamentalSeriesResponse,
    GenieResponse,
    SyncFundamentalsResponse,
)
from src.constants import KST
from src.container import ApplicationContainer
from src.service.fundamental_service import FundamentalService
from src.service.fundamental_sync_service import FundamentalSyncService

router = APIRouter(tags=["fundamentals"])


@router.post("/fundamentals/sync/kr-stock", response_model=GenieResponse[SyncFundamentalsResponse])
@inject
def sync_kr_stock_fundamentals(
        date_str: str | None = Query(default=None, alias="date", pattern=r"^\d{8}$"),
        service: FundamentalSyncService = Depends(Provide[ApplicationContainer.fundamental_sync_service]),
) -> GenieResponse[SyncFundamentalsResponse]:
    """일자별 KR 주식 펀더멘털을 pykrx에서 가져와 DB와 수동 동기화. date 미지정 시 오늘(KST)."""
    target_date = datetime.strptime(date_str, "%Y%m%d").date() if date_str else datetime.now(KST).date()
    result = service.sync(target_date)
    return GenieResponse(data=SyncFundamentalsResponse(date=target_date, **asdict(result)))


@router.get("/fundamentals", response_model=GenieResponse[FundamentalSeriesResponse])
@inject
def get_fundamentals(
        ticker: str = Query(min_length=1, max_length=20, description="ticker 코드"),
        from_: str | None = Query(default=None, alias="from", pattern=r"^\d{8}$"),
        to: str | None = Query(default=None, pattern=r"^\d{8}$"),
        service: FundamentalService = Depends(Provide[ApplicationContainer.fundamental_service]),
) -> GenieResponse[FundamentalSeriesResponse]:
    """종목별 펀더멘털 시계열 (date 오름차순). 종목 미발견 시 404."""
    from_date = datetime.strptime(from_, "%Y%m%d").date() if from_ else None
    to_date = datetime.strptime(to, "%Y%m%d").date() if to else None
    t, rows = service.get_time_series(ticker, from_date, to_date)
    return GenieResponse(
        data=FundamentalSeriesResponse(
            ticker=t.ticker,
            name=t.name,
            points=[FundamentalPoint.model_validate(r) for r in rows],
        )
    )
