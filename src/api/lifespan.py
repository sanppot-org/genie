"""FastAPI 앱 lifespan 이벤트"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from src.scheduled_tasks.schedules import get_schedules
from src.scheduled_tasks.tasks import run_strategies

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI 앱 lifespan 이벤트 - 스케줄러 시작 및 종료 관리"""

    # 스케줄러 설정 — DB pool(30) 안에서 worker를 명시. DB-heavy task는 시간이
    # staggered되어 동시 실행 거의 없으므로 5로 충분. job_defaults는 누락 정책
    # 명시화: coalesce(밀린 trigger 합치기) + max_instances=1(겹침 방지) +
    # misfire_grace_time=60(1분 늦은 실행도 허용).
    schedules = get_schedules()

    scheduler = BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(max_workers=5)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
    )
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
