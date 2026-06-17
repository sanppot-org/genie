"""미국 워치리스트 종목 등록 스크립트 (FDR StockListing으로 이름·거래소 자동 해석).

사용:
    uv run python scripts/register_us_tickers.py --symbols AAPL,MSFT,NVDA

캔들 백필(backfill_us_daily_candles.py)의 선행 단계. 멱등(재실행 안전).
ENV_PROFILE에 따라 대상 DB 결정 — 로컬만 채우려면 ENV_PROFILE=local 명시.
"""

import argparse
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register US stock tickers via FDR StockListing.")
    parser.add_argument("--symbols", required=True, help="콤마 구분 심볼 (예: AAPL,MSFT,NVDA)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    service = ApplicationContainer().us_stock_ticker_service()
    result = service.register(symbols)
    logger.info(
        "등록 완료 registered=%d updated=%d skipped_unknown=%d skipped=%s",
        result.registered, result.updated, result.skipped_unknown, result.skipped,
    )


if __name__ == "__main__":
    main()
