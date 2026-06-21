"""무한매수법 백테스트 러너 (로컬 DB adj 일봉 사용).

사용:
    ENV_PROFILE=local uv run python scripts/backtest_infinite_buying.py --ticker TQQQ --base-gap 15 \
        --start 20200101 --end 20241231 --allocation 10000 --division 40

선행: 해당 티커 일봉이 stock_daily_candles에 백필돼 있어야 한다(register_us_tickers.py + backfill_us_daily_candles.py).
adj_close/adj_high가 있으면 그것을, 없으면 close/high를 사용한다.
"""

import argparse
from datetime import datetime
import logging

from src.container import ApplicationContainer
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.infinite_buying.backtest import BacktestConfig, DailyBar, run_backtest

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest infinite-buying strategy on local adj daily candles.")
    parser.add_argument("--ticker", required=True, help="종목 코드 (예: TQQQ)")
    parser.add_argument("--base-gap", type=float, required=True, help="종목별 최대 괴리율 (TQQQ=15, SOXL=20)")
    parser.add_argument("--sell-limit-pct", type=float, default=None, help="지정가매도 %% (기본: base-gap과 동일)")
    parser.add_argument("--division", type=int, default=40, help="분할수 (기본 40)")
    parser.add_argument("--allocation", type=float, default=10000.0, help="할당금액 (기본 10000)")
    parser.add_argument("--start", default=None, help="시작일 YYYYMMDD")
    parser.add_argument("--end", default=None, help="종료일 YYYYMMDD")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from_date = datetime.strptime(args.start, "%Y%m%d").date() if args.start else None
    to_date = datetime.strptime(args.end, "%Y%m%d").date() if args.end else None
    sell_limit_pct = args.sell_limit_pct if args.sell_limit_pct is not None else args.base_gap

    database = ApplicationContainer().database()
    with database.session_scope() as session:
        ticker = TickerRepository(session).find_by_ticker(args.ticker)
        if ticker is None or ticker.id is None:
            raise SystemExit(f"티커 미등록: {args.ticker} (register_us_tickers.py로 먼저 등록)")
        rows = StockDailyCandleRepository(session).find_by_ticker(ticker.id, from_date, to_date)

    bars = [
        DailyBar(
            date=r.date,
            high=r.adj_high if r.adj_high is not None else r.high,
            close=r.adj_close if r.adj_close is not None else r.close,
        )
        for r in rows
    ]
    if not bars:
        raise SystemExit(f"일봉 데이터 없음: {args.ticker} (backfill_us_daily_candles.py로 백필)")

    config = BacktestConfig(
        division=args.division,
        base_gap=args.base_gap,
        sell_limit_pct=sell_limit_pct,
        allocation=args.allocation,
    )
    result = run_backtest(bars, config)

    logger.info("=== 무한매수법 백테스트: %s (%s ~ %s, %d거래일) ===", args.ticker, bars[0].date, bars[-1].date, result.num_days)
    logger.info("총수익률: %.2f%%", result.total_return * 100)
    logger.info("MDD: %.2f%%", result.max_drawdown * 100)
    logger.info("사이클 수: %d", result.num_cycles)
    logger.info("매수 체결: %d건 / 매도 체결: %d건", result.num_buys, result.num_sells)
    logger.info("최종 자산: %.2f (할당 %.2f)", result.final_equity, args.allocation)


if __name__ == "__main__":
    main()
