"""자사주 보유 비율 백필 스크립트 (정기보고서 단위).

사용:
    # 2015~2024 사업보고서(연 1회) 백필
    uv run python scripts/backfill_treasury_stocks.py --start-year 2015 --end-year 2024

    # 모든 보고서(사업/반기/Q1/Q3) 백필
    uv run python scripts/backfill_treasury_stocks.py --start-year 2015 --end-year 2024 --all-reports

DART OpenAPI 분당 1,000건 제한 안에서 충분히 안전. 멱등 UPSERT라 중복 실행 OK.
ENV_PROFILE에 따라 적재 대상 DB가 결정됨.
"""

import argparse
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)

REPRT_CODES_ALL = ("11013", "11012", "11014", "11011")  # Q1, 반기, Q3, 사업
REPRT_CODES_ANNUAL_ONLY = ("11011",)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill stock_treasury_stocks per (year, reprt_code).")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--all-reports", action="store_true",
                        help="사업보고서뿐만 아니라 분기/반기까지 모두 백필")
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise SystemExit("--start-year must be <= --end-year")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    container = ApplicationContainer()
    service = container.treasury_stock_sync_service()

    reprt_codes = REPRT_CODES_ALL if args.all_reports else REPRT_CODES_ANNUAL_ONLY

    total_upserted = 0
    total_no_data = 0
    total_failure = 0
    failed_periods = 0

    for year in range(args.start_year, args.end_year + 1):
        for reprt_code in reprt_codes:
            try:
                result = service.sync_period(year, reprt_code)
                logger.info(
                    "OK   year=%d reprt=%s upserted=%d no_data=%d failure=%d",
                    year, reprt_code, result.upserted,
                    result.skipped_no_data, result.skipped_failure,
                )
                total_upserted += result.upserted
                total_no_data += result.skipped_no_data
                total_failure += result.skipped_failure
            except Exception as e:
                logger.exception("FAIL year=%d reprt=%s: %s", year, reprt_code, e)
                failed_periods += 1

    logger.info(
        "백필 완료: upserted=%d skipped_no_data=%d skipped_failure=%d failed_periods=%d",
        total_upserted, total_no_data, total_failure, failed_periods,
    )


if __name__ == "__main__":
    main()
