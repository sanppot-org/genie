"""FastAPI 서버 - VolatilityStrategy 수동 매도 API + 스케줄러 통합"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.container import ApplicationContainer
from src.logging_config import setup_logging
from src.scheduled_tasks.tasks import (
    check_upbit_status,
    report,
    run_strategies,
    update_bithumb_krw,
    update_data,
    update_upbit_krw,
)
from src.scheduler_config import ScheduleConfig
from src.strategy.config import VolatilityBreakoutConfig
from src.strategy.volatility_strategy import VolatilityStrategy

# Better Stack 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)

# DI 컨테이너 초기화
container = ApplicationContainer()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI 앱 lifespan 이벤트 - 스케줄러 시작 및 종료 관리"""
    # 시작: Upbit 상태 확인 및 스케줄러 설정
    logger.info("API 서버 시작 - Upbit 상태 확인 중...")
    check_upbit_status()

    # 스케줄러 설정 (BackgroundScheduler 사용)
    schedules = [
        ScheduleConfig(
            func=report,
            trigger=CronTrigger(hour="7-21", minute=56, day_of_week="mon-fri"),
            id="update_report",
            name="리포트 업데이트",
        ),
        ScheduleConfig(
            func=update_upbit_krw,
            trigger=CronTrigger(hour=23, minute=15),
            id="update_upbit_krw",
            name="Upbit KRW 잔고 업데이트",
        ),
        ScheduleConfig(
            func=update_bithumb_krw,
            trigger=CronTrigger(hour=23, minute=15),
            id="update_bithumb_krw",
            name="Bithumb KRW 잔고 업데이트",
        ),
        ScheduleConfig(
            func=run_strategies,
            trigger=IntervalTrigger(minutes=5),
            id="crypto_trading",
            name="암호화폐 자동 매매",
        ),
        ScheduleConfig(
            func=update_data,
            trigger=IntervalTrigger(minutes=1),
            id="update_data",
            name="구글 시트 데이터 업데이트",
        ),
    ]

    scheduler = BackgroundScheduler()
    for schedule in schedules:
        scheduler.add_job(**schedule.to_add_job_kwargs())

    # 스케줄러 시작
    scheduler.start()
    logger.info("암호화폐 자동 매매 스케줄러 시작 (백그라운드)")

    # 즉시 한 번 실행
    run_strategies()

    yield

    # 종료: 스케줄러 정리
    logger.info("API 서버 종료 - 스케줄러 종료 중...")
    scheduler.shutdown()
    logger.info("스케줄러 종료 완료")


# FastAPI 앱 생성 (lifespan 이벤트 포함)
app = FastAPI(title="Genie Trading Strategy API", version="1.0.0", lifespan=lifespan)


class SellRequest(BaseModel):
    """매도 요청 모델"""

    ticker: str | None = None  # None이면 컨테이너의 기본값 사용


class SellResponse(BaseModel):
    """매도 응답 모델"""

    success: bool
    message: str
    executed_volume: float | None = None
    remaining_volume: float | None = None


def _create_volatility_strategy(ticker: str) -> VolatilityStrategy:
    """VolatilityStrategy 인스턴스를 생성합니다.

    Args:
        ticker: 거래 티커 (예: "KRW-BTC")

    Returns:
        VolatilityStrategy 인스턴스
    """
    # tasks_context에서 설정 값 가져오기
    tasks_ctx = container.tasks_context()
    total_balance = tasks_ctx.total_balance

    # ticker별 할당 금액 계산 (균등 분배)
    num_tickers = len(tasks_ctx.tickers)
    allocated_balance = total_balance / num_tickers

    # VolatilityBreakoutConfig 생성
    config = VolatilityBreakoutConfig(
        ticker=ticker,
        total_balance=total_balance,
        allocated_balance=allocated_balance,
    )

    # VolatilityStrategy 생성
    return VolatilityStrategy(
        order_executor=container.order_executor(),
        clock=container.clock(),
        collector=container.data_collector(),
        cache_manager=container.cache_manager(),
        config=config,
    )


@app.get("/")
def root() -> dict[str, str]:
    """루트 엔드포인트"""
    return {"message": "Genie Trading Strategy API"}


@app.get("/health")
def health() -> dict[str, str]:
    """헬스체크 엔드포인트"""
    return {"status": "ok"}


@app.post("/api/strategy/sell", response_model=SellResponse)
def sell_strategy(request: SellRequest) -> SellResponse:
    """변동성 돌파 전략 수동 매도 엔드포인트

    Args:
        request: 매도 요청 (ticker 선택적)

    Returns:
        매도 결과

    Raises:
        HTTPException: 매도 실패 시
    """
    # ticker 결정 (요청에 없으면 첫 번째 ticker 사용)
    tasks_ctx = container.tasks_context()
    ticker = request.ticker if request.ticker else tasks_ctx.tickers[0]

    # ticker 유효성 검증
    if ticker not in tasks_ctx.tickers:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 ticker입니다. 사용 가능한 ticker: {tasks_ctx.tickers}",
        )

    try:
        # VolatilityStrategy 생성
        strategy = _create_volatility_strategy(ticker)

        # manual_sell 실행
        result = strategy.manual_sell()

        # 응답 생성
        return SellResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"매도 실행 중 오류 발생: {e!s}") from e
