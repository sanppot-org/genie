"""스케줄 작업 설정"""

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import AppConfig
from src.scheduled_tasks.tasks import (
    readjust_kr_stock_splits,
    report,
    resync_all_adjusted_candles,
    sync_kr_stock_buybacks,
    sync_kr_stock_cancellations,
    sync_kr_stock_daily_candles,
    sync_kr_stock_dividends,
    sync_kr_stock_financial_ratios,
    sync_kr_stock_fundamentals,
    sync_kr_stock_income_statements,
    sync_kr_stock_tickers,
    sync_kr_stock_treasury_stocks,
    sync_us_stock_daily_candles,
    update_bithumb_krw,
    update_data,
)
from src.scheduler_config import ScheduleConfig


def get_schedules() -> list[ScheduleConfig]:
    """스케줄 작업 목록을 반환합니다.

    `ENABLE_REPORT=false`면 리포트 업데이트 잡을 제외한다.

    Returns:
        스케줄 설정 리스트
    """
    config = AppConfig()
    schedules: list[ScheduleConfig] = []

    if config.enable_report:
        schedules.append(
            ScheduleConfig(
                func=report,
                trigger=CronTrigger(hour="7-21", minute=56, day_of_week="mon-fri"),
                id="update_report",
                name="리포트 업데이트",
            )
        )

    schedules.extend([
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
            func=sync_us_stock_daily_candles,
            trigger=CronTrigger(hour=7, minute=30, day_of_week="tue-sat"),
            id="sync_us_stock_daily_candles",
            name="미국 주식 일봉 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_dividends,
            trigger=CronTrigger(hour=17, minute=5, day_of_week="mon-fri"),
            id="sync_kr_stock_dividends",
            name="한국 주식 배당 이력 동기화",
        ),
        ScheduleConfig(
            func=readjust_kr_stock_splits,
            trigger=CronTrigger(hour=17, minute=10, day_of_week="mon-fri"),
            id="readjust_kr_stock_splits",
            name="한국 주식 분할 감지 수정주가 재보정",
        ),
        ScheduleConfig(
            func=resync_all_adjusted_candles,
            trigger=CronTrigger(month="1,4,7,10", day=1, hour=3, minute=0),
            id="resync_all_adjusted_candles",
            name="한국 주식 수정주가 전종목 재백필(분기 안전망)",
            misfire_grace_time=3600,  # 03:00 재시작/부하로 인한 분기 누락 방지(1시간 유예)
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
        ScheduleConfig(
            func=sync_kr_stock_cancellations,
            trigger=CronTrigger(day_of_week="mon", hour=19, minute=30),
            id="sync_kr_stock_cancellations",
            name="한국 주식 주식소각결정 공시 동기화",
        ),
        ScheduleConfig(
            func=sync_kr_stock_financial_ratios,
            trigger=CronTrigger(day_of_week="mon", hour=19, minute=45),
            id="sync_kr_stock_financial_ratios",
            name="한국 주식 재무비율 동기화",
        ),
    ])

    return schedules
