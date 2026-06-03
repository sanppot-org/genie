"""KR 주식 수정주가(adjusted) 백필·동기화 서비스.

기존 `stock_daily_candles`의 원주가(KRX)는 불변 보존하고, 종목별로 네이버 수정주가를
조회해 `adj_*` 컬럼만 채운다. 단건(API/스크립트 --ticker)과 전종목 배치(스크립트)를 모두 지원.

패턴(income_statement_sync_service와 동형):
- `Database` 주입 + **종목당 독립 `session_scope` 커밋**, 네이버 호출은 **트랜잭션 밖**.
- 청크 경계 = 1종목 (종목별 UPDATE 모델이라 여러 종목 묶음 청크는 무의미).
- 멱등(같은 값 재적용) + 종목 단위라 중단 후 재개 안전.

주의: 네이버 수정주가 일봉은 ~2014년부터 제공 → 그 이전 row는 adj NULL로 남고 조회 시
원주가 폴백. 2014 이전 분할 종목은 부분 보정(`partial`)으로 로깅해 가시화한다.
"""

from dataclasses import dataclass
from datetime import date, datetime
import logging
import time

from src.common.data_adapter import DataSource
from src.constants import KST, AssetType
from src.database.database import Database
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_daily_candle_client import PykrxDailyCandleClient
from src.service.exceptions import ExceptionCode, GenieError

logger = logging.getLogger(__name__)

# 네이버 일봉이 ~2014부터라 넉넉히 과거부터 요청하고 기존 row만 매칭(미존재는 무시).
_BACKFILL_START = date(1990, 1, 1)


@dataclass(frozen=True)
class AdjustedBackfillResult:
    """단일 종목 수정주가 백필 결과."""

    ticker: str
    fetched: int            # 네이버 응답 row 수(거래정지 제외)
    updated: int            # adj_* 갱신된 DB row 수
    existing: int           # 종목의 기존 원주가 row 수
    from_date: date | None
    to_date: date | None

    @property
    def partial(self) -> bool:
        """기존 row 중 일부만 보정됨 → 네이버 미커버 구간 존재(예: 2014 이전)."""
        return self.existing > 0 and self.updated < self.existing


@dataclass(frozen=True)
class AdjustedSyncResult:
    """전종목 수정주가 백필 결과 통계."""

    ticker_count: int       # 대상 종목 수
    skipped_already: int    # only_stale로 skip(이미 adj 보유)
    api_attempted: int      # 네이버 호출 시도 종목 수
    api_failed: int         # 호출/처리 실패 종목 수
    tickers_updated: int    # 1건 이상 갱신된 종목 수
    rows_updated: int       # 총 갱신 row 수
    partial_tickers: int    # 부분 보정 종목 수(updated < existing)
    failed_tickers: list[str]


class AdjustedCandleSyncService:
    """종목별 네이버 수정주가를 `adj_*` 컬럼에 채우는 백필/동기화."""

    def __init__(
        self,
        database: Database,
        client: PykrxDailyCandleClient,
        throttle_sec: float = 0.3,
    ) -> None:
        self._database = database
        self._client = client
        self._throttle_sec = throttle_sec

    # ----- 단건 (API + 스크립트 --ticker) -----
    def backfill_one(self, ticker_code: str, now: date | None = None) -> AdjustedBackfillResult:
        """종목 코드 하나의 수정주가를 백필. 종목 미발견 시 404."""
        to_date = now or datetime.now(KST).date()
        ticker_id = self._resolve_ticker_id(ticker_code)
        fetched, updated, existing = self._process_ticker(ticker_id, ticker_code, to_date)
        result = AdjustedBackfillResult(
            ticker=ticker_code, fetched=fetched, updated=updated, existing=existing,
            from_date=_BACKFILL_START, to_date=to_date,
        )
        if result.partial:
            logger.warning(
                "수정주가 부분 보정 ticker=%s updated=%d/%d (네이버 미커버 구간 존재)",
                ticker_code, updated, existing,
            )
        return result

    # ----- 전종목 배치 (스크립트) -----
    def sync(
        self,
        only_stale: bool = False,
        ticker_codes: list[str] | None = None,
        now: date | None = None,
    ) -> AdjustedSyncResult:
        """전(또는 지정) KR_STOCK 종목 수정주가 백필.

        only_stale=True면 이미 adj_close가 1건이라도 있는 종목은 skip(재개용).
        주의: only_stale은 '신규 분할 소급 재보정' 감지가 아님 — 그건 2b 분할감지 담당.
        """
        to_date = now or datetime.now(KST).date()
        targets = self._load_targets(ticker_codes)
        skip_ids = self._already_adjusted_ids() if only_stale else set()

        skipped = api_attempted = api_failed = 0
        tickers_updated = rows_updated = partial_tickers = 0
        failed: list[str] = []

        for ticker_id, code in targets:
            if ticker_id in skip_ids:
                skipped += 1
                continue
            api_attempted += 1
            try:
                fetched, updated, existing = self._process_ticker(ticker_id, code, to_date)
            except Exception:
                logger.exception("수정주가 백필 실패 ticker=%s", code)
                api_failed += 1
                failed.append(code)
                continue
            if updated > 0:
                tickers_updated += 1
                rows_updated += updated
            if existing > 0 and updated < existing:
                partial_tickers += 1
                logger.warning("수정주가 부분 보정 ticker=%s updated=%d/%d", code, updated, existing)
            if self._throttle_sec > 0:
                time.sleep(self._throttle_sec)

        result = AdjustedSyncResult(
            ticker_count=len(targets), skipped_already=skipped,
            api_attempted=api_attempted, api_failed=api_failed,
            tickers_updated=tickers_updated, rows_updated=rows_updated,
            partial_tickers=partial_tickers, failed_tickers=failed,
        )
        logger.info(
            "전종목 수정주가 백필 완료 targets=%d skipped=%d attempted=%d failed=%d "
            "tickers_updated=%d rows_updated=%d partial=%d",
            result.ticker_count, result.skipped_already, result.api_attempted, result.api_failed,
            result.tickers_updated, result.rows_updated, result.partial_tickers,
        )
        return result

    # ----- 공통 -----
    def _process_ticker(self, ticker_id: int, ticker_code: str, to_date: date) -> tuple[int, int, int]:
        """네이버 조회(트랜잭션 밖) → 종목 row 로드 → adj_* 갱신 → 커밋. (fetched, updated, existing)."""
        adjusted = self._client.fetch_adjusted_by_ticker(ticker_code, _BACKFILL_START, to_date)
        mapping = {a.date: (a.open, a.high, a.low, a.close, a.volume) for a in adjusted}
        with self._database.session_scope() as session:
            repo = StockDailyCandleRepository(session)
            rows = repo.find_by_ticker(ticker_id)
            existing = len(rows)
            updated = repo.update_adjusted_from_rows(rows, mapping)
        return len(adjusted), updated, existing

    def _resolve_ticker_id(self, ticker_code: str) -> int:
        with self._database.session_scope() as session:
            ticker = TickerRepository(session).find_by_ticker(ticker_code)
            if ticker is None or ticker.id is None:
                raise GenieError(code=ExceptionCode.NOT_FOUND, id=ticker_code)
            return ticker.id

    def _load_targets(self, ticker_codes: list[str] | None) -> list[tuple[int, str]]:
        """대상 (ticker_id, code) 목록을 짧은 세션에서 추출 (KR_STOCK, PYKRX)."""
        wanted = set(ticker_codes) if ticker_codes is not None else None
        with self._database.session_scope() as session:
            tickers = TickerRepository(session).find_by_data_source(DataSource.PYKRX)
            return [
                (t.id, t.ticker)
                for t in tickers
                if t.asset_type == AssetType.KR_STOCK and t.id is not None
                and (wanted is None or t.ticker in wanted)
            ]

    def _already_adjusted_ids(self) -> set[int]:
        with self._database.session_scope() as session:
            return StockDailyCandleRepository(session).ticker_ids_with_adjusted()
