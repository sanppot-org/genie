"""전략 엔드포인트"""
# ruff: noqa: B008

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import SellResponse
from src.container import ApplicationContainer
from src.scheduled_tasks.context import ScheduledTasksContext
from src.strategy.factory import create_volatility_strategy

router = APIRouter()


@router.post("/strategy/sell/{ticker}", response_model=SellResponse)
@inject
def sell_strategy(
        ticker: str,
        tasks_ctx: ScheduledTasksContext = Depends(Provide[ApplicationContainer.tasks_context]),
) -> SellResponse:
    """변동성 돌파 전략 수동 매도 엔드포인트

    Args:
        ticker: 매도할 티커 (예: KRW-BTC)
        tasks_ctx: 스케줄 작업 컨텍스트 (자동 주입)

    Returns:
        매도 결과

    Raises:
        HTTPException: 매도 실패 시
    """
    # ticker 유효성 검증
    if ticker not in tasks_ctx.tickers:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 ticker입니다. 사용 가능한 ticker: {tasks_ctx.tickers}",
        )

    try:
        # VolatilityStrategy 생성
        strategy = create_volatility_strategy(ticker)

        # manual_sell 실행
        result = strategy.manual_sell()

        # 응답 생성
        return SellResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"매도 실행 중 오류 발생: {e!s}") from e
