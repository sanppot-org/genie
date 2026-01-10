"""Candle 데이터 수집 API 엔드포인트"""
# ruff: noqa: B008

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from src.api.schemas import CollectCandlesRequest, CollectCandlesResponse, GenieResponse
from src.container import ApplicationContainer
from src.service.candle_service import CandleService
from src.service.ticker_service import TickerService

router = APIRouter(tags=["candles"])


@router.post("/candles/collect", response_model=GenieResponse[CollectCandlesResponse])
@inject
def collect_minute1_candles(
        request: CollectCandlesRequest,
        candle_service: CandleService = Depends(Provide[ApplicationContainer.candle_service]),
        ticker_service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[CollectCandlesResponse]:
    """1분봉 데이터 수집

    수집 모드:
    - INCREMENTAL (기본): DB 최신 이후만 수집
    - FULL: 전체 수집
    - BACKFILL: DB 가장 오래된 이전만 수집
    """
    # ticker_id로 DB 검증 (없으면 GenieError.not_found 발생)
    ticker = ticker_service.get_by_id(request.ticker_id)

    total_saved = candle_service.collect_minute1_candles(
        ticker=ticker,
        to=request.to,
        batch_size=request.batch_size,
        mode=request.mode,
    )

    return GenieResponse(
        data=CollectCandlesResponse(
            total_saved=total_saved,
            ticker_id=request.ticker_id,
            ticker=ticker.ticker,
            mode=request.mode,
        )
    )
