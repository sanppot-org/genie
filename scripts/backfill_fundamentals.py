"""펀더멘털 일자 범위 백필 스크립트.

사용:
    uv run python scripts/backfill_fundamentals.py --start 20240101 --end 20240131

휴장일(EmptyPykrxResponseError)은 skip + log. 다른 에러는 해당 일자만 실패로 처리하고
다음 일자 계속 진행. 운영 task와 달리 Slack 알림 없음 (수동 실행 가정).

ENV_PROFILE에 따라 적재 대상 DB가 결정됨. 로컬 docker만 채우려면 `ENV_PROFILE=local` 명시.
"""

import argparse
from collections.abc import Iterator
from datetime import date, datetime, timedelta
import logging

from src.container import ApplicationContainer
from src.providers.pykrx_fundamental_client import KrxClosedDayError
from src.providers.pykrx_ticker_client import EmptyPykrxResponseError

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill stock_fundamentals over a date range.")
    parser.add_argument("--start", required=True, help="YYYYMMDD")
    parser.add_argument("--end", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y%m%d").date()
    end = datetime.strptime(args.end, "%Y%m%d").date()
    if start > end:
        raise SystemExit("--start must be <= --end")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    container = ApplicationContainer()
    service = container.fundamental_sync_service()

    succeeded = skipped = failed = 0
    for d in _date_range(start, end):
        if d.weekday() >= 5:  # Sat/Sun
            skipped += 1
            continue
        try:
            result = service.sync(d)
            logger.info(
                "OK   %s upserted=%d skipped_unmapped=%d",
                d, result.upserted, result.skipped_unmapped,
            )
            succeeded += 1
        except (KrxClosedDayError, EmptyPykrxResponseError) as e:
            logger.info("SKIP %s (%s)", d, e)
            skipped += 1
        except Exception as e:
            logger.exception("FAIL %s: %s", d, e)
            failed += 1

    logger.info("백필 완료: succeeded=%d skipped=%d failed=%d", succeeded, skipped, failed)


def _date_range(start: date, end: date) -> Iterator[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


if __name__ == "__main__":
    main()
