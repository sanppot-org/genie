"""FastAPI 서버 - Genie Trading Strategy API"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.exception_handlers import handle_genie_error, handle_unhandled_exception
from src.api.lifespan import lifespan
from src.api.middleware import DBSessionMiddleware
from src.api.routes import (
    candle,
    dividend,
    fundamental,
    health,
    income_statement,
    screening,
    strategy,
    ticker,
)
from src.config import AppConfig
from src.container import ApplicationContainer
from src.logging_config import setup_logging
from src.scheduled_tasks.scope import configure_db_scoped
from src.service.exceptions import GenieError

# Better Stack 로깅 설정
setup_logging()

# DI Container 초기화 - wiring 자동 적용
container = ApplicationContainer()

# 앱 설정 로드
app_config = AppConfig()

# FastAPI 앱 생성
app = FastAPI(
    title="Genie Trading Strategy API",
    version="1.0.0",
    lifespan=lifespan if app_config.enable_scheduler else None,
)

# CORS — 프론트(web/) dev/배포 origin 허용. 로컬 임의 포트는 regex로 매칭.
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.cors_allow_origins,
    allow_origin_regex=app_config.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 요청/task 스코프 DB 세션 (커넥션 누수 차단) — container.database는
# override 가능한 provider라 테스트와 일관. 스케줄러 task용 @db_scoped 데코레이터도
# 동일 provider를 사용하므로 부팅 시 1회 등록.
app.add_middleware(DBSessionMiddleware, database_provider=container.database)
configure_db_scoped(container.database)

# 예외 핸들러 등록
app.add_exception_handler(GenieError, handle_genie_error)
app.add_exception_handler(Exception, handle_unhandled_exception)

# 라우터 등록
app.include_router(health.router)
app.include_router(strategy.router, prefix="/api")
app.include_router(ticker.router, prefix="/api")
app.include_router(candle.router, prefix="/api")
app.include_router(fundamental.router, prefix="/api")
app.include_router(dividend.router, prefix="/api")
app.include_router(income_statement.router, prefix="/api")
app.include_router(screening.router, prefix="/api")
