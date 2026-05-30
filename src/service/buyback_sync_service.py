"""자기주식 취득·처분 공시 동기화 서비스 — DART event → `stock_buyback_events`.

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
from src.database.models import StockBuybackEvent
from src.database.stock_buyback_event_repository import StockBuybackEventRepository
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import BuybackEvent, DartCompanyClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuybackSyncResult:
    """sync 결과 통계."""

    tickers: int            # 대상 KR_STOCK 수
    received: int           # 응답 row 수 (취득+처분 합산)
    upserted: int           # 실제 DB에 쓴 row 수 (= received, 파싱 OK)
    skipped_failure: int    # 네트워크 오류 등으로 호출 실패한 종목 수


class BuybackSyncService:
    """DART 자기주식 취득·처분 공시를 `stock_buyback_events` 테이블에 동기화.

    절차:
    1) `tickers` 중 PYKRX & KR_STOCK 만 추출 (짧은 session_scope)
    2) 각 종목별로 `자기주식취득`, `자기주식처분` 두 키워드 호출 (트랜잭션 밖) → 통합 이벤트 리스트
    3) StockBuybackEvent 엔티티 빌드
    4) 독립 session_scope로 bulk_upsert 커밋
    """

    def __init__(
            self,
            database: Database,
            client: DartCompanyClient,
    ) -> None:
        self._database = database
        self._client = client

    def sync(self, from_date: date, to_date: date) -> BuybackSyncResult:
        """KR_STOCK 전종목에 대해 기간 내 자기주식 취득·처분 공시 동기화."""
        targets = self._load_targets()

        entities: list[StockBuybackEvent] = []
        skipped_failure = 0

        for ticker_id, code in targets:
            try:
                events = self._client.fetch_buyback_events(code, from_date, to_date)
            except Exception as e:
                logger.warning(
                    "자사주 공시 조회 실패 ticker=%s from=%s to=%s: %s",
                    code, from_date, to_date, e,
                )
                skipped_failure += 1
                continue

            entities.extend(_to_entities(ticker_id, events))

        with self._database.session_scope() as session:
            StockBuybackEventRepository(session).bulk_upsert(entities)

        logger.info(
            "자사주 공시 동기화 완료 from=%s to=%s tickers=%d received=%d upserted=%d skipped_failure=%d",
            from_date, to_date, len(targets), len(entities), len(entities), skipped_failure,
        )
        return BuybackSyncResult(
            tickers=len(targets),
            received=len(entities),
            upserted=len(entities),
            skipped_failure=skipped_failure,
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


def _to_entities(ticker_id: int, events: list[BuybackEvent]) -> list[StockBuybackEvent]:
    return [
        StockBuybackEvent(
            ticker_id=ticker_id,
            rcept_no=ev.rcept_no,
            event_type=ev.event_type,
            resolution_date=ev.resolution_date,
            planned_shares=ev.planned_shares,
            planned_amount=ev.planned_amount,
            period_start=ev.period_start,
            period_end=ev.period_end,
            purpose=ev.purpose,
        )
        for ev in events
    ]
