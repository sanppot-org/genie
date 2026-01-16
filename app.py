"""FastAPI 서버 - Genie Trading Strategy API"""

from fastapi import FastAPI

from src.api.exception_handlers import handle_exception
from src.api.lifespan import lifespan
from src.api.routes import candle, exchange, health, strategy, ticker
from src.config import AppConfig
from src.container import ApplicationContainer
from src.logging_config import setup_logging
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

# 예외 핸들러 등록
app.add_exception_handler(GenieError, handle_exception)

# 라우터 등록
app.include_router(health.router)
app.include_router(strategy.router, prefix="/api")
app.include_router(ticker.router, prefix="/api")
app.include_router(exchange.router, prefix="/api")
app.include_router(candle.router, prefix="/api")
