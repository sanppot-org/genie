"""손익계산서 동기화 서비스 — KIS income_statement → `stock_income_statements`.

대량(전종목 × 2주기) 수집. 핵심 안전장치(설계 검토 반영):
- KIS API 호출 루프를 **DB 트랜잭션 밖**에서 수행하고, **청크 단위로 독립 session_scope**를
  열어 커밋 → 장기 idle-in-transaction / QueuePool 고갈 회피.
- 증분 가드: 이미 최신 결산기를 커버한 종목은 skip(정상 cron 호출량 감소). 백필은 skip_current=False.
- best-effort: 종목별 API 실패는 카운트 후 진행.
"""

from dataclasses import dataclass
from datetime import date
import logging
from time import sleep

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import StockIncomeStatement
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.database.ticker_repository import TickerRepository
from src.providers.kis_income_statement_client import (
    PERIOD_ANNUAL,
    PERIOD_QUARTER,
    IncomeStatementRow,
    KisIncomeStatementClient,
)

logger = logging.getLogger(__name__)

_PERIODS = (PERIOD_ANNUAL, PERIOD_QUARTER)


@dataclass(frozen=True)
class IncomeStatementSyncResult:
    """sync 결과 통계 (의미 분리)."""

    ticker_count: int          # 대상 KR_STOCK 수
    skipped_current: int       # 증분 가드로 skip한 종목 수
    api_calls_attempted: int   # 시도한 (ticker, period) 호출 수
    api_calls_failed: int      # 실패한 호출 수
    rows_received: int         # 파싱된 결산기 행 수
    rows_upserted: int         # 커밋 성공 청크의 행 수
    chunks_committed: int      # 커밋 성공 청크 수
    chunks_failed: int         # 커밋 실패 청크 수


class IncomeStatementSyncService:
    """KIS 손익계산서를 `stock_income_statements`에 동기화."""

    def __init__(
            self,
            database: Database,
            kis_client: KisIncomeStatementClient,
            chunk_size: int = 200,
            throttle_sec: float = 0.3,
    ) -> None:
        self._database = database
        self._kis = kis_client
        self._chunk_size = chunk_size
        self._throttle_sec = throttle_sec  # KIS 초당 거래건수 제한(EGW00201) 회피용 호출 간격

    def sync(self, skip_current: bool = True, now: date | None = None) -> IncomeStatementSyncResult:
        """active KR_STOCK 전종목 손익계산서 동기화.

        Args:
            skip_current: True면 이미 최신 분기를 커버한 종목 skip(정상 cron). 백필은 False.
            now: 증분 가드 기준일(테스트용). 미지정 시 호출 시점.
        """
        targets = self._load_targets()
        today = now or date.today()
        latest_q = self._latest_by_ticker(PERIOD_QUARTER) if skip_current else {}
        latest_a = self._latest_by_ticker(PERIOD_ANNUAL) if skip_current else {}
        expected_q = _latest_expected_quarter_stac_yymm(today)
        expected_a = _latest_expected_annual_stac_yymm(today)

        buffer: list[StockIncomeStatement] = []
        ticker_count = 0
        skipped_current = 0
        api_calls_attempted = 0
        api_calls_failed = 0
        rows_received = 0
        rows_upserted = 0
        chunks_committed = 0
        chunks_failed = 0

        for ticker_id, code in targets:
            ticker_count += 1

            # 분기·연간 둘 다 최신 결산기를 커버할 때만 skip (한쪽만 적재된 종목 누락 방지).
            if (
                skip_current
                and latest_q.get(ticker_id, "") >= expected_q
                and latest_a.get(ticker_id, "") >= expected_a
            ):
                skipped_current += 1
                continue

            for period in _PERIODS:
                api_calls_attempted += 1
                try:
                    rows = self._kis.fetch(code, period)
                except Exception as e:
                    logger.warning("손익계산서 조회 실패 ticker=%s period=%s: %s", code, period, e)
                    api_calls_failed += 1
                    continue
                finally:
                    if self._throttle_sec > 0:
                        sleep(self._throttle_sec)  # 초당 거래건수 제한 회피
                rows_received += len(rows)
                buffer.extend(_to_entities(ticker_id, rows))

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

        result = IncomeStatementSyncResult(
            ticker_count=ticker_count,
            skipped_current=skipped_current,
            api_calls_attempted=api_calls_attempted,
            api_calls_failed=api_calls_failed,
            rows_received=rows_received,
            rows_upserted=rows_upserted,
            chunks_committed=chunks_committed,
            chunks_failed=chunks_failed,
        )
        logger.info(
            "손익계산서 동기화 완료 tickers=%d skipped_current=%d api_attempt=%d api_fail=%d "
            "rows_received=%d rows_upserted=%d chunks_ok=%d chunks_fail=%d",
            result.ticker_count, result.skipped_current, result.api_calls_attempted,
            result.api_calls_failed, result.rows_received, result.rows_upserted,
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

    def _latest_by_ticker(self, period_type: str) -> dict[int, str]:
        with self._database.session_scope() as session:
            return StockIncomeStatementRepository(session).latest_stac_yymm_by_ticker(period_type)

    def _commit_chunk(self, entities: list[StockIncomeStatement]) -> tuple[int, bool]:
        """청크를 독립 트랜잭션으로 커밋. (반영 행 수, 성공 여부)."""
        try:
            with self._database.session_scope() as session:
                StockIncomeStatementRepository(session).bulk_upsert(entities)
            return len(entities), True
        except Exception:
            logger.exception("손익계산서 청크 커밋 실패 (rows=%d)", len(entities))
            return 0, False


def _to_entities(ticker_id: int, rows: list[IncomeStatementRow]) -> list[StockIncomeStatement]:
    return [
        StockIncomeStatement(
            ticker_id=ticker_id,
            period_type=r.period_type,
            stac_yymm=r.stac_yymm,
            sale_account=r.sale_account,
            sale_cost=r.sale_cost,
            sale_totl_prfi=r.sale_totl_prfi,
            bsop_prti=r.bsop_prti,
            op_prfi=r.op_prfi,
            thtr_ntin=r.thtr_ntin,
        )
        for r in rows
    ]


def _latest_expected_quarter_stac_yymm(today: date) -> str:
    """가장 최근 제출 마감이 지난 분기 보고서의 결산년월(YYYYMM) — 분기 증분 가드 기준.

    treasury `_latest_reprt_period`와 동일 마감 매핑(결산일+45/90일+buffer):
    - 4/8~5/21: 전년말(YYYY-1 12) / 5/22~8/21: 당년 Q1(YYYY 03)
    - 8/22~11/21: 반기(YYYY 06) / 11/22~: Q3(YYYY 09) / 그 외: 전년 Q3(YYYY-1 09)
    """
    y = today.year
    if today >= date(y, 11, 22):
        return f"{y}09"
    if today >= date(y, 8, 22):
        return f"{y}06"
    if today >= date(y, 5, 22):
        return f"{y}03"
    if today >= date(y, 4, 8):
        return f"{y - 1}12"
    return f"{y - 1}09"


def _latest_expected_annual_stac_yymm(today: date) -> str:
    """가장 최근 제출 마감이 지난 사업보고서(연간)의 결산년월(YYYYMM) — 연간 증분 가드 기준.

    사업보고서 마감(12월 결산 기준 3/31 + buffer) 후 전년 연간(YYYY-1 12)이 확정.
    그 전이면 전전년(YYYY-2 12).
    """
    y = today.year
    if today >= date(y, 4, 8):
        return f"{y - 1}12"
    return f"{y - 2}12"
