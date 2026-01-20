"""Candle 데이터 API 엔드포인트"""
# ruff: noqa: B008
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.api.schemas import (
    CandleData,
    CollectCandlesRequest,
    CollectCandlesResponse,
    GenieResponse,
    QueryCandlesRequest,
    QueryCandlesResponse,
)
from src.container import ApplicationContainer
from src.service.candle_query_service import CandleQueryService
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
        start=request.start,
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


@router.get("/candles", response_model=GenieResponse[QueryCandlesResponse])
@inject
def query_candles(
        request: Annotated[QueryCandlesRequest, Query()],
        candle_query_service: CandleQueryService = Depends(Provide[ApplicationContainer.candle_query_service]),
        ticker_service: TickerService = Depends(Provide[ApplicationContainer.ticker_service]),
) -> GenieResponse[QueryCandlesResponse]:
    """캔들 데이터 조회

    Args:
        ticker_id: 티커 ID
        interval: 캔들 간격 (1m, 5m, 10m, 30m, 1h, 4h, 1d, 1w, 1M)
        count: 조회할 캔들 개수 (기본값: 100)
        end_time: 종료 시간 (해당 시간 이전 데이터 조회, UTC)
    """
    # ticker_id로 DB 검증 (없으면 GenieError.not_found 발생)
    ticker = ticker_service.get_by_id(request.ticker_id)

    # 캔들 데이터 조회
    df = candle_query_service.get_candles(
        ticker=ticker,
        interval=request.interval,
        count=request.count,
        end_time=request.end_time,
    )

    # DataFrame → CandleData 리스트 변환
    candles = [
        CandleData(
            timestamp=row.Index.to_pydatetime(),  # type: ignore[union-attr]
            local_time=row.local_time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in df.itertuples()
    ]

    return GenieResponse(
        data=QueryCandlesResponse(
            ticker_id=request.ticker_id,
            ticker=ticker.ticker,
            interval=request.interval,
            count=len(candles),
            candles=candles,
        )
    )
