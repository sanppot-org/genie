"""stock_dividends 중복 라벨 정리 — 같은 (ticker_id, record_date, dps) 그룹 정규화.

KIS가 분기 배당을 "중간"·"분기" 두 라벨로 응답해 라벨만 다른 row가 동시에
적재되는 케이스가 있다. 그룹별로 우선순위(QUARTERLY > INTERIM > SETTLE) 최상위
1건만 남기고 나머지를 삭제한다.

사용:
    uv run python scripts/cleanup_dividend_duplicates.py            # dry-run
    uv run python scripts/cleanup_dividend_duplicates.py --apply    # 실제 삭제

ENV_PROFILE에 따라 대상 DB가 바뀐다. 실행 전 출력되는 호스트를 반드시 확인할 것.
"""

import argparse
from collections import defaultdict
from datetime import date

from src.config import DatabaseConfig
from src.database.database import Database
from src.database.models import StockDividend
from src.service.dividend_sync_service import KIND_PRIORITY


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup duplicate dividend kind labels.")
    parser.add_argument("--apply", action="store_true", help="실제 삭제 (기본은 dry-run)")
    args = parser.parse_args()

    db_config = DatabaseConfig()
    print(f"대상 DB: {db_config.postgres_host}:{db_config.postgres_port}/{db_config.postgres_db}")
    if args.apply:
        print("⚠️  --apply 모드: 실제 DELETE를 실행합니다.")

    db = Database(db_config)
    session = db.get_session()
    try:
        rows: list[StockDividend] = session.query(StockDividend).all()
        groups: dict[tuple[int, date, float], list[StockDividend]] = defaultdict(list)
        for r in rows:
            groups[(r.ticker_id, r.record_date, r.dps)].append(r)

        dup_groups = [items for items in groups.values() if len(items) > 1]
        to_delete: list[StockDividend] = []
        for items in dup_groups:
            items.sort(key=lambda r: KIND_PRIORITY.get(r.kind, 0), reverse=True)
            to_delete.extend(items[1:])

        print(f"총 row: {len(rows)}건")
        print(f"중복 그룹: {len(dup_groups)}건")
        print(f"삭제 대상: {len(to_delete)}건")

        if dup_groups:
            print("\n샘플 5건:")
            for items in dup_groups[:5]:
                ticker_id, rd, dps = items[0].ticker_id, items[0].record_date, items[0].dps
                kinds = [r.kind for r in items]
                print(f"  ticker_id={ticker_id} record_date={rd} dps={dps}: {kinds} → {items[0].kind} 유지")

        if not to_delete:
            print("\n정리할 중복 없음.")
            return

        if not args.apply:
            print("\nDry-run — --apply 추가 시 실제 삭제.")
            return

        for r in to_delete:
            session.delete(r)
        session.commit()
        print(f"\n✅ 삭제 완료: {len(to_delete)}건")
    finally:
        session.close()


if __name__ == "__main__":
    main()
