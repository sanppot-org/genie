"""Ticker CRUD API 엔드포인트"""
# ruff: noqa: B008

from dataclasses import asdict

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.api.schemas import GenieResponse, SyncTickersResponse, TickerCreate, TickerResponse
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
def get_all_tickers(
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[list[TickerResponse]]:
    """전체 ticker 조회"""
    tickers = service.get_all()
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
