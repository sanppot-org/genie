import logging

from src.container import ApplicationContainer
from src.logging_config import setup_logging
from src.scheduled_tasks.tasks import (
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
container = ApplicationContainer()  # DI Container 초기화 및 자동 와이어링


def main() -> None:
    check_upbit_status()

    # 스케줄러 설정
    scheduler = setup_scheduler(
        report_func=report,
        update_upbit_krw_func=update_upbit_krw,
        update_bithumb_krw_func=update_bithumb_krw,
        run_strategies_func=run_strategies,
        update_data_func=update_data,
    )

    # 즉시 한 번 실행
    run_strategies()

    try:
        # 스케줄러 시작 (블로킹)
        logger.info("암호화폐 자동 매매 스케줄러 시작 (1분마다 실행)")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")


if __name__ == "__main__":
    main()
