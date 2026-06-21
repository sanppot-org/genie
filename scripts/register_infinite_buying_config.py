"""무한매수법 종목 설정 등록 스크립트.

사용:
    ENV_PROFILE=local uv run python scripts/register_infinite_buying_config.py \
        --ticker TQQQ --exchange NAS --base-gap 15 --sell-limit-pct 15 --allocation 10000 --division 40

ticker.exchange(KIS EXCD: NAS/NYS/AMS)를 설정하고 infinite_buying_config를 upsert한다.
선행: 해당 ticker가 tickers에 등록돼 있어야 함(register_us_tickers.py).
"""

import argparse
import logging

from src.container import ApplicationContainer
from src.database.models import InfiniteBuyingConfig
from src.database.ticker_repository import TickerRepository
from src.infinite_buying.repository import InfiniteBuyingConfigRepository

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register infinite-buying config for a ticker.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--exchange", required=True, choices=["NAS", "NYS", "AMS"], help="KIS EXCD")
    parser.add_argument("--base-gap", type=float, required=True)
    parser.add_argument("--sell-limit-pct", type=float, default=None)
    parser.add_argument("--allocation", type=float, default=10000.0)
    parser.add_argument("--division", type=int, default=40)
    parser.add_argument("--compounding", default="half", choices=["simple", "half", "full"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sell_limit_pct = args.sell_limit_pct if args.sell_limit_pct is not None else args.base_gap

    database = ApplicationContainer().database()
    with database.session_scope() as session:
        ticker = TickerRepository(session).find_by_ticker(args.ticker)
        if ticker is None or ticker.id is None:
            raise SystemExit(f"티커 미등록: {args.ticker} (register_us_tickers.py로 먼저 등록)")
        ticker.exchange = args.exchange  # 거래소코드 설정(실주문 필수)
        InfiniteBuyingConfigRepository(session).save(InfiniteBuyingConfig(
            ticker_id=ticker.id, division=args.division, base_gap=args.base_gap,
            allocation=args.allocation, compounding=args.compounding,
            sell_limit_pct=sell_limit_pct, active=True,
        ))
    logger.info("무한매수법 설정 등록 완료: %s (exchange=%s, base_gap=%s, div=%d)", args.ticker, args.exchange, args.base_gap, args.division)


if __name__ == "__main__":
    main()
