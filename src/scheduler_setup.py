"""스케줄러 설정 모듈

스케줄 설정과 초기화 로직을 캡슐화합니다.
"""

from collections.abc import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.scheduler_config import ScheduleConfig


def setup_scheduler(
        report_func: Callable,
        update_upbit_krw_func: Callable,
        update_bithumb_krw_func: Callable,
        run_strategies_func: Callable,
        update_data_func: Callable,
) -> BlockingScheduler:
    """스케줄러를 설정하고 반환

    Args:
        report_func: 리포트 업데이트 함수
        update_upbit_krw_func: Upbit KRW 잔고 업데이트 함수
        update_bithumb_krw_func: Bithumb KRW 잔고 업데이트 함수
        run_strategies_func: 암호화폐 자동 매매 함수
        update_data_func: 구글 시트 업데이트 함수

    Returns:
        설정된 BlockingScheduler 인스턴스
    """
    schedules = [
        ScheduleConfig(
            func=report_func,
            trigger=CronTrigger(hour="7-21", minute=56),
            id="update_report",
            name="리포트 업데이트",
        ),
        ScheduleConfig(
            func=update_upbit_krw_func,
            trigger=CronTrigger(hour=23, minute=15),
            id="update_upbit_krw",
            name="Upbit KRW 잔고 업데이트",
        ),
        ScheduleConfig(
            func=update_bithumb_krw_func,
            trigger=CronTrigger(hour=23, minute=15),
            id="update_bithumb_krw",
            name="Bithumb KRW 잔고 업데이트",
        ),
        ScheduleConfig(
            func=run_strategies_func,
            trigger=IntervalTrigger(minutes=5),
            id="crypto_trading",
            name="암호화폐 자동 매매",
        ),
        ScheduleConfig(
            func=update_data_func,
            trigger=IntervalTrigger(minutes=1),
            id="update_data",
            name="구글 시트 데이터 업데이트",
        ),
    ]

    scheduler = BlockingScheduler()
    for schedule in schedules:
        scheduler.add_job(**schedule.to_add_job_kwargs())

    return scheduler
