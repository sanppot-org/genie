"""자사주 보유 비율 동기화 서비스 — DART `stockTotqySttus` → `stock_treasury_stocks`.

핵심 안전장치(income_statement_sync_service / cancellation_sync_service와 동일):
- DART API 호출 루프를 **DB 트랜잭션 밖**에서 수행하고, 마지막에 **독립 session_scope**로
  bulk_upsert 커밋 → standalone 백필 스크립트에서도 커밋 보장(롤백 방지).
- best-effort: 종목별 API 실패는 카운트 후 진행.
"""

from dataclasses import dataclass
from datetime import date
import logging

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import StockTreasuryStock
from src.database.stock_treasury_stock_repository import StockTreasuryStockRepository
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import DartCompanyClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TreasuryStockSyncResult:
    """sync 결과 통계."""

    tickers: int            # 대상 KR_STOCK 수
    upserted: int           # 실제 DB에 쓴 row 수
    skipped_no_data: int    # DART 응답 빈/합계 행 없음 (정상 — 미발행 등)
    skipped_failure: int    # 네트워크 오류 등으로 호출 실패
    bsns_year: int          # 호출한 사업연도
    reprt_code: str         # 호출한 보고서 코드


class TreasuryStockSyncService:
    """DART 자사주 보유 비율을 `stock_treasury_stocks` 테이블에 동기화.

    절차:
    1) 호출 시점(today) 기준 가장 최근 제출 완료된 (bsns_year, reprt_code) 산출
    2) `tickers` 중 PYKRX & KR_STOCK 만 추출 (짧은 session_scope) → 각 종목별 DART 호출(트랜잭션 밖)
    3) StockTreasuryStock 엔티티 빌드
    4) 독립 session_scope로 bulk_upsert 커밋
    """

    def __init__(
            self,
            database: Database,
            client: DartCompanyClient,
    ) -> None:
        self._database = database
        self._client = client

    def sync(self, target_date: date) -> TreasuryStockSyncResult:
        """오늘 시점에서 가장 최근 보고서를 KR_STOCK 전종목에 대해 동기화."""
        bsns_year, reprt_code = _latest_reprt_period(target_date)
        return self.sync_period(bsns_year, reprt_code)

    def sync_period(self, bsns_year: int, reprt_code: str) -> TreasuryStockSyncResult:
        """특정 (bsns_year, reprt_code) 명시 호출 — backfill 용도."""
        targets = self._load_targets()

        entities: list[StockTreasuryStock] = []
        skipped_no_data = 0
        skipped_failure = 0

        for ticker_id, code in targets:
            try:
                status = self._client.fetch_treasury_stock_status(
                    code, bsns_year, reprt_code,
                )
            except Exception as e:
                logger.warning(
                    "자사주 조회 실패 ticker=%s bsns_year=%d reprt_code=%s: %s",
                    code, bsns_year, reprt_code, e,
                )
                skipped_failure += 1
                continue

            if status is None:
                skipped_no_data += 1
                continue

            ratio = status.treasury_shares / status.issued_shares * 100
            entities.append(StockTreasuryStock(
                ticker_id=ticker_id,
                stlm_dt=status.stlm_dt,
                reprt_code=status.reprt_code,
                issued_shares=status.issued_shares,
                treasury_shares=status.treasury_shares,
                treasury_ratio=ratio,
                rcept_no=status.rcept_no,
            ))

        with self._database.session_scope() as session:
            StockTreasuryStockRepository(session).bulk_upsert(entities)

        logger.info(
            "자사주 동기화 완료 bsns_year=%d reprt_code=%s tickers=%d upserted=%d skipped_no_data=%d skipped_failure=%d",
            bsns_year, reprt_code, len(targets), len(entities), skipped_no_data, skipped_failure,
        )
        return TreasuryStockSyncResult(
            tickers=len(targets),
            upserted=len(entities),
            skipped_no_data=skipped_no_data,
            skipped_failure=skipped_failure,
            bsns_year=bsns_year,
            reprt_code=reprt_code,
        )

    def _load_targets(self) -> list[tuple[int, str]]:
        """active KR_STOCK의 (ticker_id, code) 목록을 짧은 세션에서 추출."""
        with self._database.session_scope() as session:
            tickers = TickerRepository(session).find_by_data_source(DataSource.PYKRX)
            return [
                (t.id, t.ticker)
                for t in tickers
                if t.asset_type == AssetType.KR_STOCK and t.active and t.id is not None
            ]


def _latest_reprt_period(today: date) -> tuple[int, str]:
    """가장 최근 제출 마감일이 지난 정기보고서 (bsns_year, reprt_code).

    DART 정기보고서 마감일 (결산일 + 45/90일) + 7일 안전 buffer로 매핑:
    - 4/8 ~ 5/21:  전년 사업보고서 (11011, 결산 12/31)
    - 5/22 ~ 8/21: 당년 1분기 (11013, 결산 3/31)
    - 8/22 ~ 11/21: 당년 반기 (11012, 결산 6/30)
    - 11/22 ~ 다음해 4/7: 당년 3분기 (11014, 결산 9/30)
    """
    y = today.year
    if today >= date(y, 11, 22):
        return (y, "11014")
    if today >= date(y, 8, 22):
        return (y, "11012")
    if today >= date(y, 5, 22):
        return (y, "11013")
    if today >= date(y, 4, 8):
        return (y - 1, "11011")
    return (y - 1, "11014")
