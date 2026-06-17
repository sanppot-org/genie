"""미국 주식 일봉 전체 히스토리 백필 스크립트.

사용:
    uv run python scripts/backfill_us_daily_candles.py                # 가능한 최대치
    uv run python scripts/backfill_us_daily_candles.py --start 20100101

등록된 US_STOCK(FDR) 종목 전체를 대상으로 한다(선행: register_us_tickers.py).
종목별 독립 커밋이라 중단 후 재개 안전. 수동 실행 가정(Slack 알림 없음).
ENV_PROFILE에 따라 대상 DB 결정 — 로컬만 채우려면 ENV_PROFILE=local 명시.
"""

import argparse
from datetime import date, datetime
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill US stock daily candles (full history).")
    parser.add_argument("--start", default=None, help="YYYYMMDD (생략 시 1990-01-01부터)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = datetime.strptime(args.start, "%Y%m%d").date() if args.start else date(1990, 1, 1)

    service = ApplicationContainer().us_stock_daily_candle_service()
    result = service.backfill(start=start)
    logger.info(
        "백필 완료 targets=%d attempted=%d failed=%d tickers_upserted=%d rows_upserted=%d failed_tickers=%s",
        result.ticker_count, result.attempted, result.failed,
        result.tickers_upserted, result.rows_upserted, result.failed_tickers,
    )


if __name__ == "__main__":
    main()
