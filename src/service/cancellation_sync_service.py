"""주식소각결정 동기화 서비스 — DART 주식소각결정 공시 → `stock_cancellation_events`.

대량(전종목 × 기간) 수집. 핵심 안전장치(income_statement_sync_service와 동일):
- DART API 호출 루프를 **DB 트랜잭션 밖**에서 수행하고, **청크 단위로 독립 session_scope**를
  열어 커밋 → 장기 idle-in-transaction / QueuePool 고갈 회피.
- best-effort: 종목별 API 실패는 카운트 후 진행.
"""

from dataclasses import dataclass
from datetime import date
import logging
from time import sleep

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import StockCancellationEvent
from src.database.stock_cancellation_event_repository import StockCancellationEventRepository
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import CancellationEvent, DartCompanyClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CancellationSyncResult:
    """sync 결과 통계 (의미 분리)."""

    ticker_count: int          # 대상 KR_STOCK 수
    api_calls_attempted: int   # 시도한 종목 호출 수
    api_calls_failed: int      # 실패한 호출 수
    rows_received: int         # 파싱된 소각 이벤트 행 수
    rows_upserted: int         # 커밋 성공 청크의 행 수
    chunks_committed: int      # 커밋 성공 청크 수
    chunks_failed: int         # 커밋 실패 청크 수


class CancellationSyncService:
    """DART 주식소각결정 공시를 `stock_cancellation_events`에 동기화."""

    def __init__(
            self,
            database: Database,
            dart_client: DartCompanyClient,
            chunk_size: int = 200,
            throttle_sec: float = 0.3,
    ) -> None:
        self._database = database
        self._dart = dart_client
        self._chunk_size = chunk_size
        self._throttle_sec = throttle_sec  # DART 분당 호출 제한 회피용 호출 간격

    def sync(self, from_date: date, to_date: date) -> CancellationSyncResult:
        """active KR_STOCK 전종목 주식소각결정 공시 동기화.

        Args:
            from_date: 시작 접수일 (포함)
            to_date: 종료 접수일 (포함)
        """
        targets = self._load_targets()

        buffer: list[StockCancellationEvent] = []
        ticker_count = 0
        api_calls_attempted = 0
        api_calls_failed = 0
        rows_received = 0
        rows_upserted = 0
        chunks_committed = 0
        chunks_failed = 0

        for ticker_id, code in targets:
            ticker_count += 1
            api_calls_attempted += 1
            try:
                events = self._dart.fetch_cancellation_events(code, from_date, to_date)
            except Exception as e:
                logger.warning("주식소각결정 조회 실패 ticker=%s: %s", code, e)
                api_calls_failed += 1
                continue
            finally:
                if self._throttle_sec > 0:
                    sleep(self._throttle_sec)  # DART 호출 제한 회피

            rows_received += len(events)
            buffer.extend(_to_entities(ticker_id, events))

            if len(buffer) >= self._chunk_size:
                committed, ok = self._commit_chunk(buffer)
                rows_upserted += committed
                chunks_committed += 1 if ok else 0
                chunks_failed += 0 if ok else 1
                buffer = []

        if buffer:
            committed, ok = self._commit_chunk(buffer)
            rows_upserted += committed
            chunks_committed += 1 if ok else 0
            chunks_failed += 0 if ok else 1

        result = CancellationSyncResult(
            ticker_count=ticker_count,
            api_calls_attempted=api_calls_attempted,
            api_calls_failed=api_calls_failed,
            rows_received=rows_received,
            rows_upserted=rows_upserted,
            chunks_committed=chunks_committed,
            chunks_failed=chunks_failed,
        )
        logger.info(
            "주식소각결정 동기화 완료 tickers=%d api_attempt=%d api_fail=%d "
            "rows_received=%d rows_upserted=%d chunks_ok=%d chunks_fail=%d",
            result.ticker_count, result.api_calls_attempted, result.api_calls_failed,
            result.rows_received, result.rows_upserted,
            result.chunks_committed, result.chunks_failed,
        )
        return result

    def _load_targets(self) -> list[tuple[int, str]]:
        """active KR_STOCK의 (ticker_id, code) 목록을 짧은 세션에서 추출."""
        with self._database.session_scope() as session:
            tickers = TickerRepository(session).find_by_data_source(DataSource.PYKRX)
            return [
                (t.id, t.ticker)
                for t in tickers
                if t.asset_type == AssetType.KR_STOCK and t.active and t.id is not None
            ]

    def _commit_chunk(self, entities: list[StockCancellationEvent]) -> tuple[int, bool]:
        """청크를 독립 트랜잭션으로 커밋. (반영 행 수, 성공 여부)."""
        try:
            with self._database.session_scope() as session:
                StockCancellationEventRepository(session).bulk_upsert(entities)
            return len(entities), True
        except Exception:
            logger.exception("주식소각결정 청크 커밋 실패 (rows=%d)", len(entities))
            return 0, False


def _to_entities(ticker_id: int, events: list[CancellationEvent]) -> list[StockCancellationEvent]:
    return [
        StockCancellationEvent(
            ticker_id=ticker_id,
            rcept_no=e.rcept_no,
            report_nm=e.report_nm,
            resolution_date=e.resolution_date,
            cancel_date=e.cancel_date,
            common_shares=e.common_shares,
            preferred_shares=e.preferred_shares,
            cancel_amount=e.cancel_amount,
            acquisition_method=e.acquisition_method,
        )
        for e in events
    ]
