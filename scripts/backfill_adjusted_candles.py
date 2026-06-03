"""KR 주식 수정주가(adjusted) 백필 스크립트.

stock_daily_candles의 원주가는 보존하고, 네이버 수정주가를 종목별로 조회해
adj_* 컬럼을 채운다(액면분할 절벽 제거용).

사용:
    # 전 KR_STOCK 백필 (전량)
    uv run python scripts/backfill_adjusted_candles.py

    # 단일 종목
    uv run python scripts/backfill_adjusted_candles.py --ticker 005930

    # 이미 adj 채워진 종목 skip (중단 후 재개)
    uv run python scripts/backfill_adjusted_candles.py --only-stale

종목당 네이버 1콜(전 기간). 종목 단위 독립 커밋이라 중단돼도 부분 보존 + 멱등 재실행 안전.
ENV_PROFILE에 따라 대상 DB가 결정됨(prod 주의). 앱 스케줄러(default executor)를
점유하지 않도록 반드시 독립 프로세스로 실행한다.

주의: 네이버 일봉은 ~2014부터 → 2014 이전 분할 종목은 부분 보정(partial)으로 로깅됨.
신규 액면분할의 과거 소급 재보정은 이 스크립트가 아니라 2b 분할감지가 담당한다.
"""

import argparse
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill adjusted prices for KR_STOCK candles.")
    parser.add_argument("--ticker", default=None, help="단일 종목 코드(미지정 시 전 KR_STOCK)")
    parser.add_argument(
        "--only-stale",
        action="store_true",
        help="이미 adj_close가 있는 종목 skip (재개용, 전량 모드에서만 유효)",
    )
    parser.add_argument("--throttle-sec", type=float, default=0.3, help="종목 간 sleep(초), 네이버 차단 회피")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    container = ApplicationContainer()
    service = container.adjusted_candle_sync_service(throttle_sec=args.throttle_sec)

    if args.ticker:
        result = service.backfill_one(args.ticker)
        logger.info(
            "단일 백필 완료: ticker=%s fetched=%d updated=%d/%d partial=%s",
            result.ticker, result.fetched, result.updated, result.existing, result.partial,
        )
        return

    result = service.sync(only_stale=args.only_stale)
    logger.info(
        "전종목 백필 완료: targets=%d skipped=%d attempted=%d failed=%d "
        "tickers_updated=%d rows_updated=%d partial=%d",
        result.ticker_count, result.skipped_already, result.api_attempted, result.api_failed,
        result.tickers_updated, result.rows_updated, result.partial_tickers,
    )
    if result.failed_tickers:
        logger.warning("실패 종목(%d): %s", len(result.failed_tickers), ",".join(result.failed_tickers))


if __name__ == "__main__":
    main()
