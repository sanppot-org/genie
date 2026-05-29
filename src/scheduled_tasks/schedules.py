"""스케줄 작업 설정"""

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.scheduled_tasks.tasks import (
    report,
    sync_kr_stock_buybacks,
    sync_kr_stock_daily_candles,
    sync_kr_stock_dividends,
    sync_kr_stock_fundamentals,
    sync_kr_stock_income_statements,
    sync_kr_stock_tickers,
    sync_kr_stock_treasury_stocks,
    update_bithumb_krw,
    update_data,
)
from src.scheduler_config import ScheduleConfig


def get_schedules() -> list[ScheduleConfig]:
    """스케줄 작업 목록을 반환합니다.

    Returns:
        스케줄 설정 리스트
    """
    return [
        ScheduleConfig(
            func=report,
            trigger=CronTrigger(hour="7-21", minute=56, day_of_week="mon-fri"),
            id="update_report",
            name="리포트 업데이트",
        ),
        ScheduleConfig(
            func=update_bithumb_krw,
            trigger=CronTrigger(hour=23, minute=15),
            id="update_bithumb_krw",
            name="Bithumb KRW 잔고 업데이트",
        ),
        ScheduleConfig(
            func=update_data,
            trigger=IntervalTrigger(minutes=1),
            id="update_data",
            name="구글 시트 데이터 업데이트",
        ),
        ScheduleConfig(
            func=sync_kr_stock_tickers,
            trigger=CronTrigger(hour=16, minute=42, day_of_week="mon-fri"),
            id="sync_kr_stock_tickers",
            name="한국 주식 종목 정보 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_fundamentals,
            trigger=CronTrigger(hour=16, minute=50, day_of_week="mon-fri"),
            id="sync_kr_stock_fundamentals",
            name="한국 주식 펀더멘털 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_daily_candles,
            trigger=CronTrigger(hour=16, minute=58, day_of_week="mon-fri"),
            id="sync_kr_stock_daily_candles",
            name="한국 주식 일봉 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_dividends,
            trigger=CronTrigger(hour=17, minute=5, day_of_week="mon-fri"),
            id="sync_kr_stock_dividends",
            name="한국 주식 배당 이력 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_treasury_stocks,
            trigger=CronTrigger(day="1,16", hour=18, minute=0),
            id="sync_kr_stock_treasury_stocks",
            name="한국 주식 자사주 보유 비율 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_buybacks,
            trigger=CronTrigger(day_of_week="mon", hour=18, minute=30),
            id="sync_kr_stock_buybacks",
            name="한국 주식 자사주 매입·처분 공시 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_income_statements,
            trigger=CronTrigger(day_of_week="mon", hour=19, minute=0),
            id="sync_kr_stock_income_statements",
            name="한국 주식 손익계산서 동기화",
        ),
    ]
