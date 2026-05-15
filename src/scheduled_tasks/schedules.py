"""스케줄 작업 설정"""

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.scheduled_tasks.tasks import (
    report,
    sync_kr_stock_tickers,
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
            trigger=CronTrigger(hour=16, minute=48, day_of_week="mon-fri"),
            id="sync_kr_stock_tickers",
            name="한국 주식 종목 정보 동기화",
        ),
    ]
