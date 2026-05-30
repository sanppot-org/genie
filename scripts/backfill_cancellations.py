"""주식소각결정 공시(자사주 소각) 백필 스크립트.

사용:
    # 최근 3년(기본) 전 active KR_STOCK 초기 적재
    uv run python scripts/backfill_cancellations.py

    # 기간 지정
    uv run python scripts/backfill_cancellations.py --start 2023-01-01 --end 2026-05-30

종목당 DART list() 1 call + 소각공시 건당 document() 1 call. 청크 단위 독립 트랜잭션
커밋이라 중단돼도 부분 보존 + 멱등 재실행 안전. ENV_PROFILE에 따라 적재 대상 DB가
결정됨(prod 주의).

앱 스케줄러(default executor)를 점유하지 않도록 반드시 독립 프로세스로 실행한다.
"""

import argparse
from datetime import date, datetime
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill stock_cancellation_events for all active KR_STOCK."
    )
    parser.add_argument("--start", type=_parse_date, default=date(2023, 1, 1), help="시작 접수일 (기본 2023-01-01)")
    parser.add_argument("--end", type=_parse_date, default=date.today(), help="종료 접수일 (기본 오늘)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    container = ApplicationContainer()
    service = container.cancellation_sync_service()

    result = service.sync(from_date=args.start, to_date=args.end)
    logger.info(
        "백필 완료: from=%s to=%s tickers=%d api_attempt=%d api_fail=%d "
        "rows_received=%d rows_upserted=%d chunks_ok=%d chunks_fail=%d",
        args.start, args.end, result.ticker_count, result.api_calls_attempted,
        result.api_calls_failed, result.rows_received, result.rows_upserted,
        result.chunks_committed, result.chunks_failed,
    )


if __name__ == "__main__":
    main()
