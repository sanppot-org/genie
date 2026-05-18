"""자기주식 취득·처분 공시 백필 스크립트.

사용:
    # 10년치 백필
    uv run python scripts/backfill_buybacks.py --start 20150101 --end 20251231

DART `event()`가 기간 검색이라 한 번에 N년치 가능. 종목당 2 calls (취득/처분).
멱등 UPSERT라 중복 실행 OK. ENV_PROFILE에 따라 적재 대상 DB가 결정됨.
"""

import argparse
from datetime import datetime
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill stock_buyback_events over a date range.")
    parser.add_argument("--start", required=True, help="YYYYMMDD")
    parser.add_argument("--end", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y%m%d").date()
    end = datetime.strptime(args.end, "%Y%m%d").date()
    if start > end:
        raise SystemExit("--start must be <= --end")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    container = ApplicationContainer()
    service = container.buyback_sync_service()

    result = service.sync(start, end)
    logger.info(
        "백필 완료: tickers=%d received=%d upserted=%d skipped_failure=%d",
        result.tickers, result.received, result.upserted, result.skipped_failure,
    )


if __name__ == "__main__":
    main()
