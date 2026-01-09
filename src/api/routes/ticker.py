"""Ticker CRUD API 엔드포인트"""
# ruff: noqa: B008

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.api.schemas import GenieResponse, TickerCreate, TickerResponse
from src.container import ApplicationContainer
from src.service.ticker_service import TickerService

router = APIRouter(tags=["tickers"])


@router.post("/tickers", response_model=GenieResponse[TickerResponse], status_code=status.HTTP_201_CREATED)
@inject
def create_or_update_ticker(
        ticker_in: TickerCreate,
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[TickerResponse]:
    """Ticker 생성 또는 업데이트 (upsert)"""
    ticker = service.upsert(ticker=ticker_in.ticker, asset_type=ticker_in.asset_type)
    return GenieResponse(data=ticker)


@router.get("/tickers", response_model=GenieResponse[list[TickerResponse]])
@inject
def get_all_tickers(
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[list[TickerResponse]]:
    """전체 ticker 조회"""
    tickers = service.get_all()
    return GenieResponse(data=tickers)


@router.get("/tickers/{ticker_id}", response_model=GenieResponse[TickerResponse])
@inject
def get_ticker(
        ticker_id: int,
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[TickerResponse]:
    """ID로 ticker 조회"""
    ticker = service.get_by_id(ticker_id)
    return GenieResponse(data=ticker)


@router.delete("/tickers/{ticker_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
def delete_ticker(
        ticker_id: int,
        service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> None:
    """ticker 삭제 (없으면 무시)"""
    service.delete(ticker_id)
