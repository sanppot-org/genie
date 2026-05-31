"""재무비율(ROE·성장률·부채비율 등) 백필 스크립트.

사용:
    # 전 active KR_STOCK 초기 적재 (증분 가드 OFF로 전량)
    uv run python scripts/backfill_financial_ratios.py

    # 증분만 (이미 최신 사업보고서 커버 종목 skip) — cron과 동일 동작 수동 실행
    uv run python scripts/backfill_financial_ratios.py --incremental

종목당 1 call(연간). 청크 단위 독립 트랜잭션 커밋이라 중단돼도 부분 보존 +
멱등 재실행 안전. ENV_PROFILE에 따라 적재 대상 DB가 결정됨(prod 주의).

앱 스케줄러(default executor)를 점유하지 않도록 반드시 독립 프로세스로 실행한다.
"""

import argparse
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill stock_financial_ratios for all active KR_STOCK.")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="이미 최신 사업보고서를 커버한 종목 skip (기본: 전량 적재)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    container = ApplicationContainer()
    service = container.financial_ratio_sync_service()

    result = service.sync(skip_current=args.incremental)
    logger.info(
        "백필 완료: tickers=%d skipped_current=%d api_attempt=%d api_fail=%d "
        "rows_received=%d rows_upserted=%d chunks_ok=%d chunks_fail=%d",
        result.ticker_count, result.skipped_current, result.api_calls_attempted,
        result.api_calls_failed, result.rows_received, result.rows_upserted,
        result.chunks_committed, result.chunks_failed,
    )


if __name__ == "__main__":
    main()
