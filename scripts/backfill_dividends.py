"""배당 이력 백필 스크립트 (10년치 권장).

사용:
    uv run python scripts/backfill_dividends.py --start 20150101 --end 20251231

KIS `ksdinfo_dividend`는 기간 단위 호출이라 1년 청크로 잘라서 결산/중간 두 번씩 호출한다.
멱등 UPSERT이므로 중복 실행에도 안전. 운영 task와 달리 Slack 알림 없음.

ENV_PROFILE에 따라 적재 대상 DB가 결정됨. 로컬 docker만 채우려면 `ENV_PROFILE=local` 명시.
"""

import argparse
from datetime import date, datetime, timedelta
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill stock_dividends over a date range.")
    parser.add_argument("--start", required=True, help="YYYYMMDD")
    parser.add_argument("--end", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y%m%d").date()
    end = datetime.strptime(args.end, "%Y%m%d").date()
    if start > end:
        raise SystemExit("--start must be <= --end")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    container = ApplicationContainer()
    service = container.dividend_sync_service()

    total_upserted = 0
    total_skipped_unmapped = 0
    total_skipped_invalid = 0
    failed_chunks = 0

    for chunk_start, chunk_end in _yearly_chunks(start, end):
        try:
            result = service.sync(chunk_start, chunk_end)
            logger.info(
                "OK   %s~%s upserted=%d skipped_unmapped=%d skipped_invalid=%d",
                chunk_start, chunk_end, result.upserted,
                result.skipped_unmapped, result.skipped_invalid,
            )
            total_upserted += result.upserted
            total_skipped_unmapped += result.skipped_unmapped
            total_skipped_invalid += result.skipped_invalid
        except Exception as e:
            logger.exception("FAIL %s~%s: %s", chunk_start, chunk_end, e)
            failed_chunks += 1

    logger.info(
        "백필 완료: upserted=%d skipped_unmapped=%d skipped_invalid=%d failed_chunks=%d",
        total_upserted, total_skipped_unmapped, total_skipped_invalid, failed_chunks,
    )


def _yearly_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """[start, end]를 1년 단위로 잘라 (chunk_start, chunk_end) 페어로 반환."""
    chunks: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        chunk_end = min(date(cur.year, 12, 31), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


if __name__ == "__main__":
    main()
