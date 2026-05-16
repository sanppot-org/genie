"""펀더멘털 동기화 API 엔드포인트."""
# ruff: noqa: B008

from dataclasses import asdict
from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.api.schemas import GenieResponse, SyncFundamentalsResponse
from src.constants import KST
from src.container import ApplicationContainer
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
