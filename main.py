import logging

from src.container import ApplicationContainer
from src.logging_config import setup_logging
from src.scheduled_tasks import (
    check_upbit_status,
    report,
    run_strategies,
    update_bithumb_krw,
    update_data,
    update_upbit_krw,
)
from src.scheduler_setup import setup_scheduler

# Better Stack 로깅 설정 (가장 먼저 실행)
setup_logging()
logger = logging.getLogger(__name__)

# DI Container 초기화
container = ApplicationContainer()

if __name__ == "__main__":
    # 필요한 컴포넌트 가져오기
    tasks_context = container.tasks_context()

    check_upbit_status(tasks_context)

    # 스케줄러 설정
    scheduler = setup_scheduler(
        report_func=lambda: report(tasks_context),
        update_upbit_krw_func=lambda: update_upbit_krw(tasks_context),
        update_bithumb_krw_func=lambda: update_bithumb_krw(tasks_context),
        run_strategies_func=lambda: run_strategies(tasks_context),
        update_data_func=lambda: update_data(tasks_context),
    )

    # 즉시 한 번 실행
    run_strategies(tasks_context)

    try:
        # 스케줄러 시작 (블로킹)
        logger.info("암호화폐 자동 매매 스케줄러 시작 (1분마다 실행)")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
