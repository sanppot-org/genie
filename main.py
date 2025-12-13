"""
⚠️ 주의: 이 파일은 스케줄러만 실행하는 레거시 방식입니다.

✅ 권장: API 서버 + 스케줄러 통합 버전 사용
   $ uv run uvicorn src.api:app --reload --port 8000

이 파일은 다음과 같은 경우에만 사용하세요:
- API 서버 없이 스케줄러만 실행하고 싶을 때
- 백업/테스트 목적

통합 API 서버는 다음을 모두 제공합니다:
- 자동 스케줄링 (5분마다 전략 실행, 1분마다 데이터 업데이트)
- 수동 매도 API (POST /api/strategy/sell)
- 헬스체크 및 모니터링
"""

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
