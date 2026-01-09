"""Candle 데이터 수집 API 엔드포인트"""
# ruff: noqa: B008

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from src.api.schemas import CollectCandlesRequest, CollectCandlesResponse, GenieResponse
from src.container import ApplicationContainer
from src.service.candle_service import CandleService

router = APIRouter(tags=["candles"])


@router.post("/candles/collect", response_model=GenieResponse[CollectCandlesResponse])
@inject
def collect_minute1_candles(
        request: CollectCandlesRequest,
        service: CandleService = Depends(Provide[ApplicationContainer.candle_service]),
) -> GenieResponse[CollectCandlesResponse]:
    """1분봉 데이터 수집

    수집 모드:
    - INCREMENTAL (기본): DB 최신 이후만 수집
    - FULL: 전체 수집
    - BACKFILL: DB 가장 오래된 이전만 수집
    """
    total_saved = service.collect_minute1_candles(
        ticker=request.ticker,
        to=request.to,
        batch_size=request.batch_size,
        mode=request.mode,
    )
    return GenieResponse(
        data=CollectCandlesResponse(
            total_saved=total_saved,
            ticker=request.ticker,
            mode=request.mode,
        )
    )
