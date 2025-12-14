"""FastAPI 앱 lifespan 이벤트"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from src.scheduled_tasks.schedules import get_schedules
from src.scheduled_tasks.tasks import check_upbit_status, run_strategies

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI 앱 lifespan 이벤트 - 스케줄러 시작 및 종료 관리"""

    # 시작: Upbit 상태 확인 및 스케줄러 설정
    logger.info("API 서버 시작 - Upbit 상태 확인 중...")
    check_upbit_status()

    # 스케줄러 설정 (BackgroundScheduler 사용)
    schedules = get_schedules()

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
