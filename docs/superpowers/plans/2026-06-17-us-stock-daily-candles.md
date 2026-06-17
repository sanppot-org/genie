# 미국 주식 일봉 수집 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관심 미국 종목의 일봉(원주가 OHLCV + 수정주가)을 FDR 주 소스로 수집해 기존 `stock_daily_candles` 테이블에 저장한다.

**Architecture:** 기존 KR 주식 파이프라인(`DailyCandleSyncService` + `AdjustedCandleSyncService`)을 미러링한다. FDR `StockListing`으로 종목을 등록(이름·거래소 자동 해석)한 뒤, `UsStockDailyClient`(FDR→yfinance 폴백)로 일봉을 받아 종목별 독립 트랜잭션으로 upsert한다. 수정주가는 `factor = AdjClose/Close` 비례 역조정으로 복원한다.

**Tech Stack:** Python 3.12, FinanceDataReader, yfinance, SQLAlchemy, Postgres(ON CONFLICT), Alembic, APScheduler, dependency-injector, pytest.

**참조 스펙:** `docs/superpowers/specs/2026-06-17-us-stock-daily-candles-design.md`

---

## File Structure

- `src/common/data_adapter.py` (수정) — `DataSource.FDR` enum 멤버 추가.
- `src/database/models.py` (수정) — `Ticker.exchange` nullable 컬럼 추가.
- `alembic/versions/018_add_exchange_to_tickers.py` (생성) — exchange 컬럼 마이그레이션.
- `src/providers/us_stock_daily_client.py` (생성) — FDR→yfinance 폴백, 일봉 정규화.
- `src/service/us_stock_ticker_service.py` (생성) — FDR StockListing 기반 종목 등록.
- `src/service/us_stock_daily_candle_service.py` (생성) — 종목별 백필/EOD upsert + 수정주가 복원.
- `src/container.py` (수정) — 신규 client/service DI 등록.
- `src/scheduled_tasks/tasks.py` (수정) — `sync_us_stock_daily_candles` task.
- `src/scheduled_tasks/schedules.py` (수정) — EOD 스케줄 등록.
- `scripts/register_us_tickers.py` (생성) — 워치리스트 일괄 등록.
- `scripts/backfill_us_daily_candles.py` (생성) — 전체 히스토리 백필.
- 테스트: `tests/providers/test_us_stock_daily_client.py`, `tests/service/test_us_stock_ticker_service.py`, `tests/service/test_us_stock_daily_candle_service.py`.

---

## Task 1: `DataSource.FDR` enum 추가

**Files:**
- Modify: `src/common/data_adapter.py:23-27`
- Test: `tests/common/test_data_source.py`

- [ ] **Step 1: Write the failing test**

Create `tests/common/test_data_source.py`:

```python
"""DataSource enum 테스트."""

from src.common.data_adapter import DataSource
from src.constants import TimeZone


def test_fdr_source_value_and_timezone() -> None:
    assert DataSource.FDR.value == "fdr"
    assert DataSource.FDR.timezone == TimeZone.NEW_YORK
    # 문자열 호환 (DB 저장값 기준 멤버 조회)
    assert DataSource("fdr") is DataSource.FDR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/common/test_data_source.py -v`
Expected: FAIL with `AttributeError: FDR` (멤버 없음)

- [ ] **Step 3: Add the enum member**

In `src/common/data_adapter.py`, add `FDR` after the `PYKRX` line (line 27):

```python
    UPBIT = ("upbit", TimeZone.SEOUL)
    BINANCE = ("binance", TimeZone.UTC)
    HANTU_D = ("hantu_domastic", TimeZone.SEOUL)
    HANTU_O = ("hantu_overseas", TimeZone.NEW_YORK)
    PYKRX = ("pykrx", TimeZone.SEOUL)
    FDR = ("fdr", TimeZone.NEW_YORK)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/common/test_data_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/common/data_adapter.py tests/common/test_data_source.py
git commit -m "feat(us-stock): add DataSource.FDR for US daily candles"
```

---

## Task 2: `Ticker.exchange` 컬럼 + 마이그레이션

**Files:**
- Modify: `src/database/models.py:159-174`
- Create: `alembic/versions/018_add_exchange_to_tickers.py`
- Test: `tests/database/test_ticker_exchange.py`

- [ ] **Step 1: Write the failing test**

Create `tests/database/test_ticker_exchange.py`:

```python
"""Ticker.exchange 컬럼 테스트 (인메모리 SQLite, 모델 기반 create_all)."""

from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository


def test_ticker_persists_exchange(session: Session) -> None:
    repo = TickerRepository(session)
    saved = repo.save(Ticker(
        ticker="AAPL", name="Apple Inc",
        asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value,
        exchange="NAS",
    ))
    assert saved.exchange == "NAS"
    # KR 종목은 NULL 허용
    kr = repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    assert kr.exchange is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/database/test_ticker_exchange.py -v`
Expected: FAIL with `TypeError: 'exchange' is an invalid keyword argument for Ticker`

- [ ] **Step 3: Add the column to the model**

In `src/database/models.py`, add the `exchange` column to `Ticker` right after the `active` column (line 166):

```python
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    exchange: Mapped[str | None] = mapped_column(String(4), nullable=True, comment="해외 거래소코드(KIS EXCD: NAS/NYS/AMS), US_STOCK만 채워짐")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/database/test_ticker_exchange.py -v`
Expected: PASS (테스트는 `Base.metadata.create_all`로 스키마 생성 → 마이그레이션 불필요)

- [ ] **Step 5: Create the Alembic migration**

Create `alembic/versions/018_add_exchange_to_tickers.py`:

```python
"""Add exchange column to tickers

Revision ID: 018_ticker_exchange
Revises: 017_adjusted_candle_columns
Create Date: 2026-06-17

해외 거래소코드(KIS EXCD: NAS/NYS/AMS) 저장 컬럼. US_STOCK만 채워지고 그 외 자산은 NULL.
nullable ADD COLUMN이라 테이블 rewrite 없는 메타데이터 변경(잠금 최소).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018_ticker_exchange"
down_revision: str | Sequence[str] | None = "017_adjusted_candle_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable exchange column."""
    op.add_column(
        "tickers",
        sa.Column("exchange", sa.String(length=4), nullable=True, comment="해외 거래소코드(KIS EXCD: NAS/NYS/AMS), US_STOCK만 채워짐"),
    )


def downgrade() -> None:
    """Drop exchange column."""
    op.drop_column("tickers", "exchange")
```

- [ ] **Step 6: Verify the migration is the new head (no DB write yet)**

Run: `uv run alembic heads`
Expected: `018_ticker_exchange (head)`

- [ ] **Step 7: Confirm DB host BEFORE applying (사용자 승인 필수)**

> ⚠️ CLAUDE.md 규칙: `alembic upgrade` 전 대상 호스트를 확인하고 사용자 승인을 받는다. `.env.dev`/`.env.prod`가 prod IP를 가리킬 수 있음.

Run: `uv run python -c "from src.config import DatabaseConfig; print(DatabaseConfig().database_url)"`
Expected: 로컬 docker(`localhost`/`127.0.0.1`)인지 확인. 로컬만 채우려면 `ENV_PROFILE=local` 명시.
**대상이 로컬 docker임을 사용자에게 명시하고 승인받은 뒤** 다음 단계로 진행. prod면 중단.

- [ ] **Step 8: Apply the migration (승인 후)**

Run: `ENV_PROFILE=local uv run alembic upgrade head`
Expected: `Running upgrade 017_adjusted_candle_columns -> 018_ticker_exchange`

- [ ] **Step 9: Commit**

```bash
git add src/database/models.py alembic/versions/018_add_exchange_to_tickers.py tests/database/test_ticker_exchange.py
git commit -m "feat(us-stock): add nullable exchange column to tickers"
```

---

## Task 3: `UsStockDailyClient` (FDR 주 → yfinance 폴백)

**Files:**
- Create: `src/providers/us_stock_daily_client.py`
- Test: `tests/providers/test_us_stock_daily_client.py`

- [ ] **Step 1: Write the failing test**

Create `tests/providers/test_us_stock_daily_client.py`:

```python
"""UsStockDailyClient 테스트 (FDR/yfinance mock)."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from src.providers.us_stock_daily_client import UsDailyBar, UsStockDailyClient


def _fdr_df() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {
            "Open": [187.15, 184.22],
            "High": [188.44, 185.88],
            "Low": [183.89, 183.43],
            "Close": [185.64, 184.25],
            "Volume": [82488700, 58414500],
            "Adj Close": [183.56, 182.19],
        },
        index=idx,
    )


def test_fetch_uses_fdr_and_normalizes() -> None:
    client = UsStockDailyClient()
    with patch("src.providers.us_stock_daily_client.fdr.DataReader", return_value=_fdr_df()) as m:
        bars = client.fetch("AAPL", date(2024, 1, 1), date(2024, 1, 10))
    m.assert_called_once()
    assert bars == [
        UsDailyBar(date=date(2024, 1, 2), open=187.15, high=188.44, low=183.89,
                   close=185.64, volume=82488700, adj_close=183.56),
        UsDailyBar(date=date(2024, 1, 3), open=184.22, high=185.88, low=183.43,
                   close=184.25, volume=58414500, adj_close=182.19),
    ]


def test_fetch_falls_back_to_yfinance_on_fdr_failure() -> None:
    client = UsStockDailyClient()
    yf_df = _fdr_df()  # 동일 컬럼 형태 (auto_adjust=False 시 Adj Close 포함)
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = yf_df
    with patch("src.providers.us_stock_daily_client.fdr.DataReader", side_effect=RuntimeError("boom")), \
         patch("src.providers.us_stock_daily_client.yf.Ticker", return_value=fake_ticker):
        bars = client.fetch("AAPL", date(2024, 1, 1), date(2024, 1, 10))
    assert len(bars) == 2
    assert bars[0].close == 185.64


def test_fetch_returns_empty_when_fdr_empty() -> None:
    client = UsStockDailyClient()
    with patch("src.providers.us_stock_daily_client.fdr.DataReader", return_value=pd.DataFrame()), \
         patch("src.providers.us_stock_daily_client.yf.Ticker", return_value=MagicMock(history=MagicMock(return_value=pd.DataFrame()))):
        bars = client.fetch("ZZZZ", date(2024, 1, 1), date(2024, 1, 10))
    assert bars == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/providers/test_us_stock_daily_client.py -v`
Expected: FAIL with `ModuleNotFoundError: src.providers.us_stock_daily_client`

- [ ] **Step 3: Write the implementation**

Create `src/providers/us_stock_daily_client.py`:

```python
"""미국 주식 일봉 조회 클라이언트 (FDR 주 소스 → yfinance 폴백).

FDR `DataReader`와 yfinance `history(auto_adjust=False)`는 둘 다
원주가 OHLCV + `Adj Close`를 한 번에 반환한다(종목당 1콜로 전체 히스토리).
FDR을 1순위로 둔다: naive date 인덱스(타임존 처리 불필요), 국내 친화.
FDR 실패/빈 응답 시 yfinance로 폴백한다. 둘 다 비면 빈 리스트.
"""

from dataclasses import dataclass
from datetime import date
import logging

import FinanceDataReader as fdr  # noqa: N813
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsDailyBar:
    """미국 주식 일봉 1행 (원주가 OHLCV + 수정 종가)."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float


class UsStockDailyClient:
    """FDR 주 소스 + yfinance 폴백 일봉 클라이언트."""

    def fetch(self, symbol: str, start: date, end: date | None = None) -> list[UsDailyBar]:
        """심볼의 일봉을 [start, end]로 조회. 실패 시 폴백, 데이터 없으면 빈 리스트."""
        df = self._try_fdr(symbol, start, end)
        if df is None or df.empty:
            df = self._try_yfinance(symbol, start, end)
        if df is None or df.empty:
            logger.warning("US 일봉 데이터 없음 symbol=%s", symbol)
            return []
        return self._normalize(df)

    def _try_fdr(self, symbol: str, start: date, end: date | None) -> pd.DataFrame | None:
        try:
            return fdr.DataReader(symbol, start, end)
        except Exception:
            logger.exception("FDR 조회 실패 symbol=%s → yfinance 폴백", symbol)
            return None

    def _try_yfinance(self, symbol: str, start: date, end: date | None) -> pd.DataFrame | None:
        try:
            return yf.Ticker(symbol).history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d") if end else None,
                auto_adjust=False,
            )
        except Exception:
            logger.exception("yfinance 조회 실패 symbol=%s", symbol)
            return None

    def _normalize(self, df: pd.DataFrame) -> list[UsDailyBar]:
        """OHLCV + Adj Close DataFrame을 UsDailyBar 리스트로 변환 (Adj Close 없으면 Close 사용)."""
        bars: list[UsDailyBar] = []
        for idx, row in df.iterrows():
            close = float(row["Close"])
            adj = float(row["Adj Close"]) if "Adj Close" in df.columns and pd.notna(row["Adj Close"]) else close
            bars.append(UsDailyBar(
                date=pd.Timestamp(idx).date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=close,
                volume=int(row["Volume"]),
                adj_close=adj,
            ))
        return bars
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/providers/test_us_stock_daily_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/providers/us_stock_daily_client.py tests/providers/test_us_stock_daily_client.py
git commit -m "feat(us-stock): add UsStockDailyClient with FDR→yfinance fallback"
```

---

## Task 4: `UsStockTickerService` (FDR StockListing 기반 종목 등록)

**Files:**
- Create: `src/service/us_stock_ticker_service.py`
- Test: `tests/service/test_us_stock_ticker_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/service/test_us_stock_ticker_service.py`:

```python
"""UsStockTickerService 테스트 (StockListing mock)."""

from unittest.mock import patch

import pandas as pd
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.ticker_repository import TickerRepository
from src.service.us_stock_ticker_service import UsStockTickerService


def _listing(symbols_names: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Symbol": [s for s, _ in symbols_names], "Name": [n for _, n in symbols_names]}
    )


def _patched_listing():
    """NASDAQ/NYSE/AMEX 별 StockListing 반환 mock."""
    mapping = {
        "NASDAQ": _listing([("AAPL", "Apple Inc"), ("NVDA", "NVIDIA Corp")]),
        "NYSE": _listing([("LLY", "Eli Lilly and Co")]),
        "AMEX": _listing([("IMO", "Imperial Oil Ltd")]),
    }
    return patch(
        "src.service.us_stock_ticker_service.fdr.StockListing",
        side_effect=lambda mkt: mapping[mkt],
    )


def test_register_enriches_name_and_exchange(db: Database, session: Session) -> None:
    service = UsStockTickerService(database=db)
    with _patched_listing():
        result = service.register(["AAPL", "LLY", "ZZZZ"])

    assert result.registered == 2
    assert result.skipped_unknown == 1
    assert "ZZZZ" in result.skipped

    repo = TickerRepository(session)
    aapl = repo.find_by_ticker("AAPL")
    assert aapl.name == "Apple Inc"
    assert aapl.exchange == "NAS"
    assert aapl.asset_type == AssetType.US_STOCK
    assert aapl.data_source == DataSource.FDR.value
    assert repo.find_by_ticker("LLY").exchange == "NYS"


def test_register_is_idempotent(db: Database, session: Session) -> None:
    service = UsStockTickerService(database=db)
    with _patched_listing():
        service.register(["AAPL"])
        result = service.register(["AAPL"])  # 두 번째 호출
    assert result.updated == 1
    assert len(TickerRepository(session).find_by_data_source(DataSource.FDR)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service/test_us_stock_ticker_service.py -v`
Expected: FAIL with `ModuleNotFoundError: src.service.us_stock_ticker_service`

- [ ] **Step 3: Write the implementation**

Create `src/service/us_stock_ticker_service.py`:

```python
"""미국 주식 종목 등록 서비스 (FDR StockListing 기반 이름·거래소 자동 해석).

워치리스트 심볼을 받아 FDR `StockListing('NASDAQ'/'NYSE'/'AMEX')`에서 이름과
거래소를 해석하고 `tickers`에 등록(US_STOCK / FDR / exchange). 목록에 없는 심볼은 skip.
캔들 수집(`UsStockDailyCandleService`)의 **선행 단계**다.

FDR 거래소명 → KIS EXCD 매핑: NASDAQ→NAS, NYSE→NYS, AMEX→AMS.
StockListing 3종은 호출 비용이 있어(총 ~15s) 인스턴스 캐시에 1회만 로드한다.
"""

from dataclasses import dataclass, field
import logging

import FinanceDataReader as fdr  # noqa: N813

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository

logger = logging.getLogger(__name__)

# FDR StockListing 시장명 → KIS EXCD
_MARKET_TO_EXCD: dict[str, str] = {"NASDAQ": "NAS", "NYSE": "NYS", "AMEX": "AMS"}


@dataclass
class UsTickerRegisterResult:
    """종목 등록 결과."""

    registered: int = 0          # 신규 등록 수
    updated: int = 0             # 기존 갱신 수
    skipped_unknown: int = 0     # FDR 목록에서 못 찾은 수
    skipped: list[str] = field(default_factory=list)


class UsStockTickerService:
    """FDR StockListing으로 미국 종목을 enrich하여 tickers에 등록."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._listing_map: dict[str, tuple[str, str]] | None = None  # symbol -> (name, excd)

    def register(self, symbols: list[str]) -> UsTickerRegisterResult:
        """심볼 리스트를 등록(또는 갱신). FDR 목록에 없는 심볼은 skip."""
        listing = self._load_listing_map()
        result = UsTickerRegisterResult()
        with self._database.session_scope() as session:
            repo = TickerRepository(session)
            for symbol in symbols:
                meta = listing.get(symbol.upper())
                if meta is None:
                    result.skipped_unknown += 1
                    result.skipped.append(symbol)
                    logger.warning("FDR 목록에 없는 미국 종목 skip symbol=%s", symbol)
                    continue
                name, excd = meta
                existing = repo.find_by_ticker(symbol)
                if existing is not None:
                    existing.name = name
                    existing.exchange = excd
                    existing.active = True
                    result.updated += 1
                else:
                    repo.save(Ticker(
                        ticker=symbol.upper(),
                        name=name,
                        asset_type=AssetType.US_STOCK,
                        data_source=DataSource.FDR.value,
                        exchange=excd,
                    ))
                    result.registered += 1
        logger.info(
            "미국 종목 등록 완료 registered=%d updated=%d skipped_unknown=%d",
            result.registered, result.updated, result.skipped_unknown,
        )
        return result

    def _load_listing_map(self) -> dict[str, tuple[str, str]]:
        """NASDAQ/NYSE/AMEX 상장목록을 1회 로드해 symbol→(name, excd) 맵 구성(캐시)."""
        if self._listing_map is not None:
            return self._listing_map
        mapping: dict[str, tuple[str, str]] = {}
        for market, excd in _MARKET_TO_EXCD.items():
            df = fdr.StockListing(market)
            for symbol, name in zip(df["Symbol"], df["Name"], strict=False):
                mapping[str(symbol).upper()] = (str(name), excd)
        self._listing_map = mapping
        return mapping
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/service/test_us_stock_ticker_service.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/service/us_stock_ticker_service.py tests/service/test_us_stock_ticker_service.py
git commit -m "feat(us-stock): add UsStockTickerService for FDR-based ticker registration"
```

---

## Task 5: `UsStockDailyCandleService` (백필/EOD upsert + 수정주가 복원)

**Files:**
- Create: `src/service/us_stock_daily_candle_service.py`
- Test: `tests/service/test_us_stock_daily_candle_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/service/test_us_stock_daily_candle_service.py`:

```python
"""UsStockDailyCandleService 통합 테스트 (인메모리 DB + UsStockDailyClient mock)."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.us_stock_daily_client import UsDailyBar, UsStockDailyClient
from src.service.us_stock_daily_candle_service import UsStockDailyCandleService


@pytest.fixture
def us_ticker(db: Database) -> int:
    session = db.get_session()
    try:
        t = TickerRepository(session).save(Ticker(
            ticker="AAPL", name="Apple Inc",
            asset_type=AssetType.US_STOCK, data_source=DataSource.FDR.value, exchange="NAS",
        ))
        session.commit()
        return t.id
    finally:
        session.close()


def _client(bars: list[UsDailyBar]) -> MagicMock:
    m = MagicMock(spec=UsStockDailyClient)
    m.fetch.return_value = bars
    return m


def test_backfill_upserts_raw_and_adjusted(db: Database, us_ticker: int) -> None:
    """원주가 OHLCV upsert + factor(AdjClose/Close)로 adj_* 복원."""
    bars = [
        # close=200, adj_close=100 → factor=0.5
        UsDailyBar(date=date(2024, 1, 2), open=210, high=220, low=190, close=200, volume=1_000_000, adj_close=100),
        # factor=1.0 (수정 없음)
        UsDailyBar(date=date(2024, 1, 3), open=205, high=215, low=200, close=210, volume=900_000, adj_close=210),
    ]
    service = UsStockDailyCandleService(database=db, client=_client(bars), throttle_sec=0)

    result = service.backfill(["AAPL"], start=date(2024, 1, 1), now=date(2024, 1, 10))

    assert result.rows_upserted == 2
    assert result.tickers_upserted == 1

    session = db.get_session()
    try:
        rows = {r.date: r for r in StockDailyCandleRepository(session).find_by_ticker(us_ticker)}
    finally:
        session.close()
    r1 = rows[date(2024, 1, 2)]
    assert r1.close == 200 and r1.open == 210      # 원주가 보존
    assert r1.adj_close == 100                      # 수정 종가
    assert r1.adj_open == 105 and r1.adj_high == 110 and r1.adj_low == 95  # OHLC * 0.5
    r2 = rows[date(2024, 1, 3)]
    assert r2.adj_close == 210 and r2.adj_open == 205  # factor=1.0


def test_backfill_skips_empty_response(db: Database, us_ticker: int) -> None:
    service = UsStockDailyCandleService(database=db, client=_client([]), throttle_sec=0)
    result = service.backfill(["AAPL"], start=date(2024, 1, 1), now=date(2024, 1, 10))
    assert result.rows_upserted == 0
    assert result.tickers_upserted == 0


def test_backfill_continues_on_one_ticker_failure(db: Database, us_ticker: int) -> None:
    """한 종목 client 예외가 배치를 막지 않음 (failed로 집계)."""
    client = MagicMock(spec=UsStockDailyClient)
    client.fetch.side_effect = RuntimeError("network down")
    service = UsStockDailyCandleService(database=db, client=client, throttle_sec=0)
    result = service.backfill(["AAPL"], start=date(2024, 1, 1), now=date(2024, 1, 10))
    assert result.failed == 1
    assert "AAPL" in result.failed_tickers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service/test_us_stock_daily_candle_service.py -v`
Expected: FAIL with `ModuleNotFoundError: src.service.us_stock_daily_candle_service`

- [ ] **Step 3: Write the implementation**

Create `src/service/us_stock_daily_candle_service.py`:

```python
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
from datetime import date, datetime
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
        start = today - __import__("datetime").timedelta(days=lookback_days)
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
```

> 참고: `sync_recent`의 `timedelta`는 모듈 상단 import로 정리해도 된다 — 구현 시 `from datetime import date, datetime, timedelta`로 바꾸고 `__import__` 라인을 `start = today - timedelta(days=lookback_days)`로 교체할 것.

- [ ] **Step 4: Clean up the timedelta import**

In `src/service/us_stock_daily_candle_service.py`, change the import line to:

```python
from datetime import date, datetime, timedelta
```

and replace the body of `sync_recent` with:

```python
    def sync_recent(self, lookback_days: int = 5, now: date | None = None) -> UsDailyCandleSyncResult:
        """최근 lookback_days 구간만 증분 동기화 (EOD 스케줄용)."""
        today = now or datetime.now(KST).date()
        start = today - timedelta(days=lookback_days)
        return self._run(None, start, today)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/service/test_us_stock_daily_candle_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/service/us_stock_daily_candle_service.py tests/service/test_us_stock_daily_candle_service.py
git commit -m "feat(us-stock): add UsStockDailyCandleService for daily backfill/EOD upsert"
```

---

## Task 6: DI 컨테이너 등록

**Files:**
- Modify: `src/container.py` (imports + providers near line 250-261)

- [ ] **Step 1: Add imports**

In `src/container.py`, add after line 64 (`from src.service.treasury_stock_sync_service import TreasuryStockSyncService`):

```python
from src.service.us_stock_daily_candle_service import UsStockDailyCandleService
from src.service.us_stock_ticker_service import UsStockTickerService
```

and after line 43 (`from src.providers.upbit_candle_client import UpbitCandleClient`):

```python
from src.providers.us_stock_daily_client import UsStockDailyClient
```

- [ ] **Step 2: Add providers**

In `src/container.py`, after the `adjusted_candle_sync_service` provider (line 261), add:

```python
    us_stock_daily_client = providers.Singleton(UsStockDailyClient)
    us_stock_ticker_service = providers.Factory(
        UsStockTickerService,
        database=database,
    )
    us_stock_daily_candle_service = providers.Factory(
        UsStockDailyCandleService,
        database=database,
        client=us_stock_daily_client,
    )
```

- [ ] **Step 3: Verify the container builds**

Run: `uv run python -c "from src.container import ApplicationContainer; c = ApplicationContainer(); print(c.us_stock_daily_candle_service); print(c.us_stock_ticker_service)"`
Expected: 두 provider 객체가 에러 없이 출력됨.

- [ ] **Step 4: Commit**

```bash
git add src/container.py
git commit -m "feat(us-stock): wire US stock services into DI container"
```

---

## Task 7: EOD 스케줄 task + 등록

**Files:**
- Modify: `src/scheduled_tasks/tasks.py` (import + new task)
- Modify: `src/scheduled_tasks/schedules.py` (import + ScheduleConfig)

- [ ] **Step 1: Add the task import**

In `src/scheduled_tasks/tasks.py`, add after line 33 (`from src.service.treasury_stock_sync_service import TreasuryStockSyncService`):

```python
from src.service.us_stock_daily_candle_service import UsStockDailyCandleService
```

- [ ] **Step 2: Add the task function**

In `src/scheduled_tasks/tasks.py`, append at the end of the file:

```python
@db_scoped
@inject
def sync_us_stock_daily_candles(
        service: UsStockDailyCandleService = Provide[ApplicationContainer.us_stock_daily_candle_service],
        slack_client: SlackClient = Provide[ApplicationContainer.slack_client],
) -> None:
    """미국 주식 일봉 EOD 증분 동기화 (미국장 마감 후, 화~토 07:30 KST).

    최근 5거래일을 멱등 UPSERT(휴장·실행 누락 방어). 종목별 독립 커밋이라
    일부 종목 실패는 배치를 막지 않고 failed로 집계 → Slack 알림.
    """
    try:
        result = service.sync_recent()
        logger.info(
            "미국 일봉 동기화 완료 targets=%d attempted=%d failed=%d tickers_upserted=%d rows_upserted=%d",
            result.ticker_count, result.attempted, result.failed,
            result.tickers_upserted, result.rows_upserted,
        )
        if result.failed_tickers:
            slack_client.send_status(
                f"미국 일봉 동기화 일부 실패({result.failed}종목): {','.join(result.failed_tickers[:20])}"
            )
    except Exception as e:
        mark_rollback_only()
        logger.exception("미국 일봉 동기화 실패")
        slack_client.send_status(f"미국 일봉 동기화 실패: {e}")
```

- [ ] **Step 3: Register the schedule**

In `src/scheduled_tasks/schedules.py`, add `sync_us_stock_daily_candles` to the import block (line 7-22):

```python
from src.scheduled_tasks.tasks import (
    readjust_kr_stock_splits,
    report,
    resync_all_adjusted_candles,
    sync_kr_stock_buybacks,
    sync_kr_stock_cancellations,
    sync_kr_stock_daily_candles,
    sync_kr_stock_dividends,
    sync_kr_stock_financial_ratios,
    sync_kr_stock_fundamentals,
    sync_kr_stock_income_statements,
    sync_kr_stock_tickers,
    sync_kr_stock_treasury_stocks,
    sync_us_stock_daily_candles,
    update_bithumb_krw,
    update_data,
)
```

and add this `ScheduleConfig` inside the `schedules.extend([...])` list (after the `sync_kr_stock_daily_candles` entry, line 77):

```python
        ScheduleConfig(
            func=sync_us_stock_daily_candles,
            trigger=CronTrigger(hour=7, minute=30, day_of_week="tue-sat"),
            id="sync_us_stock_daily_candles",
            name="미국 주식 일봉 동기화",
        ),
```

> 타이밍 근거: 미국장 마감 16:00 ET → 데이터 안정화 후 다음날 07:30 KST. 월~금 미국 세션은 KST 화~토에 대응하므로 `day_of_week="tue-sat"`.

- [ ] **Step 4: Verify schedules load**

Run: `uv run python -c "from src.scheduled_tasks.schedules import get_schedules; ids=[s.id for s in get_schedules()]; print('sync_us_stock_daily_candles' in ids)"`
Expected: `True`

- [ ] **Step 5: Run ruff + mypy on changed files**

Run: `uv run ruff check src/ && uv run mypy src/`
Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
git add src/scheduled_tasks/tasks.py src/scheduled_tasks/schedules.py
git commit -m "feat(us-stock): schedule daily US candle EOD sync (tue-sat 07:30 KST)"
```

---

## Task 8: 등록·백필 스크립트

**Files:**
- Create: `scripts/register_us_tickers.py`
- Create: `scripts/backfill_us_daily_candles.py`

- [ ] **Step 1: Create the ticker registration script**

Create `scripts/register_us_tickers.py`:

```python
"""미국 워치리스트 종목 등록 스크립트 (FDR StockListing으로 이름·거래소 자동 해석).

사용:
    uv run python scripts/register_us_tickers.py --symbols AAPL,MSFT,NVDA

캔들 백필(backfill_us_daily_candles.py)의 선행 단계. 멱등(재실행 안전).
ENV_PROFILE에 따라 대상 DB 결정 — 로컬만 채우려면 ENV_PROFILE=local 명시.
"""

import argparse
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register US stock tickers via FDR StockListing.")
    parser.add_argument("--symbols", required=True, help="콤마 구분 심볼 (예: AAPL,MSFT,NVDA)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    service = ApplicationContainer().us_stock_ticker_service()
    result = service.register(symbols)
    logger.info(
        "등록 완료 registered=%d updated=%d skipped_unknown=%d skipped=%s",
        result.registered, result.updated, result.skipped_unknown, result.skipped,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the backfill script**

Create `scripts/backfill_us_daily_candles.py`:

```python
"""미국 주식 일봉 전체 히스토리 백필 스크립트.

사용:
    uv run python scripts/backfill_us_daily_candles.py                # 가능한 최대치
    uv run python scripts/backfill_us_daily_candles.py --start 20100101

등록된 US_STOCK(FDR) 종목 전체를 대상으로 한다(선행: register_us_tickers.py).
종목별 독립 커밋이라 중단 후 재개 안전. 수동 실행 가정(Slack 알림 없음).
ENV_PROFILE에 따라 대상 DB 결정 — 로컬만 채우려면 ENV_PROFILE=local 명시.
"""

import argparse
from datetime import date, datetime
import logging

from src.container import ApplicationContainer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill US stock daily candles (full history).")
    parser.add_argument("--start", default=None, help="YYYYMMDD (생략 시 1990-01-01부터)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = datetime.strptime(args.start, "%Y%m%d").date() if args.start else date(1990, 1, 1)

    service = ApplicationContainer().us_stock_daily_candle_service()
    result = service.backfill(start=start)
    logger.info(
        "백필 완료 targets=%d attempted=%d failed=%d tickers_upserted=%d rows_upserted=%d failed_tickers=%s",
        result.ticker_count, result.attempted, result.failed,
        result.tickers_upserted, result.rows_upserted, result.failed_tickers,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test the scripts compile/import**

Run: `uv run python -c "import ast; ast.parse(open('scripts/register_us_tickers.py').read()); ast.parse(open('scripts/backfill_us_daily_candles.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Run ruff on scripts**

Run: `uv run ruff check scripts/register_us_tickers.py scripts/backfill_us_daily_candles.py`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/register_us_tickers.py scripts/backfill_us_daily_candles.py
git commit -m "feat(us-stock): add register + backfill scripts for US daily candles"
```

---

## Task 9: 전체 검증 + 문서 갱신

**Files:**
- Modify: `docs/stock.md` (미국 일봉 수집 항목 추가)

- [ ] **Step 1: Full lint/type/test sweep**

Run: `uv run ruff check src/ tests/ scripts/ && uv run mypy src/ && uv run pytest tests/ -q`
Expected: all pass (신규 테스트 8개 포함).

- [ ] **Step 2: Document the new pipeline in docs/stock.md**

In `docs/stock.md`, add a section describing: 미국 주식 일봉 수집(FDR 주 → yfinance 폴백), 종목 등록(`register_us_tickers.py`), 백필(`backfill_us_daily_candles.py`), EOD 스케줄(화~토 07:30 KST), 저장 위치(`stock_daily_candles`, 원주가+수정주가).

- [ ] **Step 3: Commit**

```bash
git add docs/stock.md
git commit -m "docs(us-stock): document US daily candle collection pipeline"
```

- [ ] **Step 4: (수동, 선택) 실데이터 검증**

워치리스트 등록 + 소규모 백필을 로컬 DB로 직접 확인:

```bash
ENV_PROFILE=local uv run python scripts/register_us_tickers.py --symbols AAPL,MSFT,NVDA
ENV_PROFILE=local uv run python scripts/backfill_us_daily_candles.py --start 20240101
```

`stock_daily_candles`에 해당 ticker_id 행과 `adj_close` 채워짐 확인.

---

## Self-Review Notes

- **Spec coverage**: 종목 등록(Task 4) / FDR→yfinance 폴백(Task 3) / 원주가+수정주가 factor 복원(Task 5) / DataSource.FDR(Task 1) / exchange 컬럼(Task 2) / EOD 스케줄(Task 7) / 백필(Task 8) / 동적 워치리스트(register 스크립트 + DB 행) — 모두 태스크에 매핑됨. 조회 API는 스펙대로 범위 밖.
- **Type consistency**: `UsDailyBar`(Task 3) 필드 ↔ `UsStockDailyCandleService._adjusted`/`_process_ticker`(Task 5) 사용 일치. `update_adjusted_from_rows`의 5-튜플 `(o,h,low,c,v:int)` 시그니처에 맞춰 adj_volume을 int로 전달. `find_by_data_source(DataSource.FDR)` 라우팅 키 일관.
- **마이그레이션 주의**: Task 2 Step 7-8 — `alembic upgrade`는 호스트 확인·사용자 승인 후에만 실행(prod 오적용 방지).
