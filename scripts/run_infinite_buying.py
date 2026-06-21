"""무한매수법 발주/대조 수동 실행 스크립트 (스케줄러 없음).

사용:
    # 발주(미국장 마감 직전): 오늘 걸 주문을 KIS에 발주
    ENV_PROFILE=local uv run python scripts/run_infinite_buying.py place
    # 대조(다음날): 전일 체결을 원장에 반영
    ENV_PROFILE=local uv run python scripts/run_infinite_buying.py reconcile --start 20260619 --end 20260619

⚠️ place는 실계좌에 실제 주문을 발주한다(REAL 계좌·실거래). 대상 계좌·환경을 반드시 확인하고 실행할 것.
"""

import argparse
from datetime import datetime
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run infinite-buying place/reconcile manually.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("place", help="오늘치 주문 발주")
    rec = sub.add_parser("reconcile", help="체결 대조")
    rec.add_argument("--start", required=True, help="YYYYMMDD")
    rec.add_argument("--end", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    service = ApplicationContainer().infinite_buying_service()

    if args.cmd == "place":
        result = service.place_daily_orders()
        logger.info(
            "발주 완료: 종목 %d, 발주 %d, exchange 누락 skip=%s, 종가 누락 skip=%s",
            result.tickers, result.placed, result.skipped_no_exchange, result.skipped_no_close,
        )
    else:
        start = datetime.strptime(args.start, "%Y%m%d").date()
        end = datetime.strptime(args.end, "%Y%m%d").date()
        result = service.reconcile_fills(start, end)
        logger.info("대조 완료: 포지션 %d, 체결반영 %d, 사이클종료 %d", result.positions, result.filled, result.cycles_closed)


if __name__ == "__main__":
    main()
