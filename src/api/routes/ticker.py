"""Ticker CRUD API 엔드포인트"""
# ruff: noqa: B008

from dataclasses import asdict

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, status

from src.api.schemas import GenieResponse, SyncTickersResponse, TickerCreate, TickerResponse
from src.constants import AssetType
from src.container import ApplicationContainer
from src.service.ticker_service import TickerService
from src.service.ticker_sync_service import TickerSyncService

router = APIRouter(tags=["tickers"])


@router.put("/tickers", response_model=GenieResponse[TickerResponse], status_code=status.HTTP_201_CREATED)
@inject
def create_or_update_ticker(
        ticker_in: TickerCreate,
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[TickerResponse]:
    """Ticker 생성 또는 업데이트 (upsert)"""
    ticker = service.upsert(ticker_in)
    return GenieResponse(data=TickerResponse.from_ticker(ticker))


@router.post("/tickers/sync/kr-stock", response_model=GenieResponse[SyncTickersResponse])
@inject
def sync_kr_stock_tickers(
        service: TickerSyncService = Depends(Provide[ApplicationContainer.ticker_sync_service]),
) -> GenieResponse[SyncTickersResponse]:
    """한국 주식/ETF 종목 정보를 pykrx에서 가져와 DB와 수동 동기화 (~20초 소요)"""
    result = service.sync_pykrx()
    return GenieResponse(data=SyncTickersResponse(**asdict(result)))


@router.get("/tickers", response_model=GenieResponse[list[TickerResponse]])
@inject
def get_tickers(
        q: str | None = Query(default=None, max_length=50, description="ticker/종목명 부분일치"),
        asset_type: AssetType | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=100),
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[list[TickerResponse]]:
    """ticker 목록. q/asset_type 미지정 시 전체. 지정 시 ILIKE 검색(active=True 한정)."""
    if q is None and asset_type is None:
        tickers = service.get_all()
    else:
        tickers = service.search(query=q, asset_type=asset_type, limit=limit)
    return GenieResponse(data=[TickerResponse.from_ticker(t) for t in tickers])


@router.get("/tickers/{ticker_id}", response_model=GenieResponse[TickerResponse])
@inject
def get_ticker(
        ticker_id: int,
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[TickerResponse]:
    """ID로 ticker 조회"""
    ticker = service.get_by_id(ticker_id)
    return GenieResponse(data=TickerResponse.from_ticker(ticker))


@router.delete("/tickers/{ticker_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
def delete_ticker(
        ticker_id: int,
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> None:
    """ticker 삭제 (없으면 무시)"""
    service.delete(ticker_id)
