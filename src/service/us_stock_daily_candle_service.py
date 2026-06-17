"""미국 주식 일봉 백필·EOD 동기화 서비스 (FDR 주 소스).

`UsStockDailyClient`로 종목별 일봉(원주가 OHLCV + Adj Close)을 받아
`stock_daily_candles`에 적재한다. 수정주가는 `factor = adj_close / close` 비례
역조정으로 adj_* 컬럼에 복원한다(원주가 불변 보존).

패턴(AdjustedCandleSyncService와 동형):
- `Database` 주입 + **종목당 독립 `session_scope` 커밋**, 외부 조회는 트랜잭션 밖.
- 종목 단위라 중단 후 재개 안전, 멱등 UPSERT.
- 한 종목 실패가 배치 전체를 막지 않음(failed 집계).

대상: tickers 중 `data_source=FDR & asset_type=US_STOCK & active=True`.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import logging
import time

from src.common.data_adapter import DataSource
from src.constants import KST, AssetType
from src.database.database import Database
from src.database.models import StockDailyCandle
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.us_stock_daily_client import UsDailyBar, UsStockDailyClient

logger = logging.getLogger(__name__)

# FDR/Stooq가 주는 가장 과거부터 요청 (실제 시작은 소스가 가진 데이터에 종속).
_BACKFILL_START = date(1990, 1, 1)


@dataclass
class UsDailyCandleSyncResult:
    """미국 일봉 동기화 결과 통계."""

    ticker_count: int = 0
    attempted: int = 0
    failed: int = 0
    tickers_upserted: int = 0
    rows_upserted: int = 0
    failed_tickers: list[str] = field(default_factory=list)


class UsStockDailyCandleService:
    """미국 주식 일봉을 종목별로 upsert (원주가 + 수정주가)."""

    def __init__(
        self,
        database: Database,
        client: UsStockDailyClient,
        throttle_sec: float = 0.5,
    ) -> None:
        self._database = database
        self._client = client
        self._throttle_sec = throttle_sec

    def backfill(
        self,
        symbols: list[str] | None = None,
        start: date = _BACKFILL_START,
        now: date | None = None,
    ) -> UsDailyCandleSyncResult:
        """전(또는 지정) 미국 종목 일봉을 start~오늘로 백필."""
        return self._run(symbols, start, now)

    def sync_recent(self, lookback_days: int = 5, now: date | None = None) -> UsDailyCandleSyncResult:
        """최근 lookback_days 구간만 증분 동기화 (EOD 스케줄용)."""
        today = now or datetime.now(KST).date()
        start = today - timedelta(days=lookback_days)
        return self._run(None, start, today)

    def _run(self, symbols: list[str] | None, start: date, now: date | None) -> UsDailyCandleSyncResult:
        to_date = now or datetime.now(KST).date()
        targets = self._load_targets(symbols)
        result = UsDailyCandleSyncResult(ticker_count=len(targets))
        for ticker_id, symbol in targets:
            result.attempted += 1
            try:
                upserted = self._process_ticker(ticker_id, symbol, start, to_date)
            except Exception:
                logger.exception("미국 일봉 백필 실패 symbol=%s", symbol)
                result.failed += 1
                result.failed_tickers.append(symbol)
                continue
            if upserted > 0:
                result.tickers_upserted += 1
                result.rows_upserted += upserted
            if self._throttle_sec > 0:
                time.sleep(self._throttle_sec)
        logger.info(
            "미국 일봉 동기화 완료 targets=%d attempted=%d failed=%d tickers_upserted=%d rows_upserted=%d",
            result.ticker_count, result.attempted, result.failed,
            result.tickers_upserted, result.rows_upserted,
        )
        return result

    def _process_ticker(self, ticker_id: int, symbol: str, start: date, to_date: date) -> int:
        """외부 조회(트랜잭션 밖) → 원주가 bulk_upsert + 수정주가 복원 → 커밋. 반환: upsert row 수."""
        bars = self._client.fetch(symbol, start, to_date)
        if not bars:
            return 0
        entities = [
            StockDailyCandle(
                ticker_id=ticker_id, date=b.date,
                open=b.open, high=b.high, low=b.low, close=b.close,
                volume=b.volume, trade_value=None,
            )
            for b in bars
        ]
        adjusted_by_date = {b.date: self._adjusted(b) for b in bars}
        with self._database.session_scope() as session:
            repo = StockDailyCandleRepository(session)
            repo.bulk_upsert(entities)
            rows = repo.find_by_ticker(ticker_id)
            repo.update_adjusted_from_rows(rows, adjusted_by_date)
        return len(entities)

    @staticmethod
    def _adjusted(bar: UsDailyBar) -> tuple[float, float, float, float, int]:
        """factor = adj_close/close 비례 역조정으로 (adj_open, adj_high, adj_low, adj_close, adj_volume)."""
        factor = bar.adj_close / bar.close if bar.close else 1.0
        adj_volume = int(round(bar.volume / factor)) if factor else bar.volume
        return (bar.open * factor, bar.high * factor, bar.low * factor, bar.adj_close, adj_volume)

    def _load_targets(self, symbols: list[str] | None) -> list[tuple[int, str]]:
        """대상 (ticker_id, symbol) 목록 (US_STOCK, FDR, active=True)."""
        wanted = {s.upper() for s in symbols} if symbols is not None else None
        with self._database.session_scope() as session:
            tickers = TickerRepository(session).find_by_data_source(DataSource.FDR)
            return [
                (t.id, t.ticker)
                for t in tickers
                if t.asset_type == AssetType.US_STOCK and t.active and t.id is not None
                and (wanted is None or t.ticker.upper() in wanted)
            ]
