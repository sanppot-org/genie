"""FastAPI 서버 - Genie Trading Strategy API"""

from fastapi import FastAPI

from src.api.lifespan import lifespan
from src.api.routes import health, strategy
from src.container import ApplicationContainer
from src.logging_config import setup_logging

# Better Stack 로깅 설정
setup_logging()

# DI Container 초기화 - wiring 자동 적용
container = ApplicationContainer()

# FastAPI 앱 생성
app = FastAPI(
    title="Genie Trading Strategy API",
    version="1.0.0",
    lifespan=lifespan,
)

# 라우터 등록
app.include_router(health.router)
app.include_router(strategy.router, prefix="/api")
