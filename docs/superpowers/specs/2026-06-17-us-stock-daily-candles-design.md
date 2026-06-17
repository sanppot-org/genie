# 미국 주식 일봉 수집 설계 (US Stock Daily Candles)

- 작성일: 2026-06-17
- 상태: 설계 확정(스펙 리뷰 대기)
- 목적: 백테스팅/분석용 미국 주식 일봉(OHLCV + 수정주가)을 수집·저장한다.

## 1. 배경 / 목표

genie는 이미 KR 주식 일봉을 `stock_daily_candles` 테이블에 pykrx(원주가) + 네이버(수정주가)로 수집한다.
동일 패턴을 미국 주식으로 확장한다. 이 데이터는 **백테스팅·조건 스크리닝 분석용**이며, 실시간 매매 피드가 아니다.

### 핵심 결정 요약

| 항목 | 결정 |
|---|---|
| 용도 | 백테스팅/분석용 **일봉** |
| 종목 범위 | 관심 종목(수십 개), **DB 기반 동적 관리** |
| 종목 등록 | **선행 필수.** FDR `StockListing`으로 심볼→(이름, 거래소) 자동 해석 |
| 주 데이터소스 | **FinanceDataReader(FDR)** → yfinance → KIS `dailyprice` 폴백 |
| 수정주가 | **원주가 + 수정주가 둘 다** 저장 (factor = AdjClose/Close) |
| 백필 깊이 | **가능한 최대치** (FDR은 종목당 전체 히스토리 1콜) |
| 저장 테이블 | 기존 `stock_daily_candles` **재사용** |
| 스키마 변경 | `DataSource.FDR` enum 추가 + `tickers.exchange` nullable 컬럼 추가 |
| 조회 API | **이번 범위 제외** (후속 작업) |

## 2. 데이터소스 결정 근거

- **FDR/yfinance vs KIS**: KIS `dailyprice`(HHDFS76240000)는 임의 미국 종목을 지원하지만 **호출당 ~100일 + tr_cont 페이징**이라 수십 종목×수년 백필이 느리고 레이트림 위험이 있다. FDR/yfinance는 **종목당 전체 히스토리를 1콜**로 받고 무료·무키이며 이미 프로젝트 의존성이다.
- **검증 결과(2026-06-17, AAPL)**: FDR `DataReader`는 `Open, High, Low, Close, Volume, Adj Close`를, yfinance `history(auto_adjust=False)`는 동일 컬럼 + `Dividends, Stock Splits`를 1콜로 반환. **원주가 + Adj Close가 한 번에** 온다.
- **FDR 1순위 이유**: naive date 인덱스(타임존 처리 불필요), 국내 친화, Stooq 백엔드가 대량 호출에 yfinance보다 덜 민감.
- **KIS는 폴백/교차검증**: 매매 브로커와 동일 소스라 체결가 일관성이 필요할 때 유용. `dailyprice`는 거래대금(tamt)도 제공해 `trade_value` 보완 가능.
- 참고: KIS `inquire_daily_chartprice`(현 `get_daily_candles`)는 **미국은 다우30·나스닥100·S&P500 한정**이라 임의 워치리스트에 부적합 → 폴백엔 `dailyprice`를 쓴다.

## 3. 아키텍처

```
[선행] 워치리스트 심볼(수십 개)
   │  UsStockTickerService.register(symbols)
   │  FDR StockListing(NASDAQ/NYSE/AMEX) → 심볼→(이름, 거래소) 맵
   ▼
DB tickers (asset_type=US_STOCK, data_source=FDR, active=True, exchange=NAS/NYS/AMS)
   │  find_by_data_source(DataSource.FDR) + active 필터
   ▼
UsStockDailyClient (신규 provider)
   │   FDR 1순위 → yfinance → KIS dailyprice 폴백
   │   normalize → DataFrame[date, open, high, low, close, volume, adj_close]
   ▼
UsStockDailyCandleService (신규 service)  ← AdjustedCandleSyncService 패턴 복제
   │   factor = adj_close / close → adj_open/high/low 복원
   │   종목별 독립 session_scope + 커밋 (멱등)
   ▼
StockDailyCandleRepository (재사용)
   │   bulk_upsert(원주가 OHLCV) + update_adjusted(adj_*)
   ▼
stock_daily_candles (재사용)
```

### 재사용 (변경 없음)
- `StockDailyCandle` 모델 (`src/database/models.py:398-432`)
- `StockDailyCandleRepository.bulk_upsert` / `update_adjusted` (`src/database/stock_daily_candle_repository.py`)
- `TickerRepository.find_by_data_source` (`src/database/ticker_repository.py:64`)
- `TickerService.upsert` + `POST /tickers` (동적 종목 등록)
- APScheduler 등록 패턴 (`src/scheduled_tasks/schedules.py`, `tasks.py`)
- 백필 스크립트 패턴 (`scripts/backfill_daily_candles.py`)

### 신규
- `UsStockTickerService` (service): **종목 등록 선행 단계.** FDR `StockListing('NASDAQ'/'NYSE'/'AMEX')`를 로드해 `심볼→(이름, 거래소)` 맵을 만들고, 워치리스트 심볼을 enrich하여 `TickerService.upsert`로 등록(`asset_type=US_STOCK, data_source=FDR, exchange=NAS/NYS/AMS`). 목록 3종은 호출 비용이 있으므로(총 ~15s) 배치당 1회 로드/캐시.
- `UsStockDailyClient` (provider): 소스 폴백 + 정규화. FDR/yfinance 호출은 기존 `src/collector/data_fetcher.py`의 재시도 래퍼 재사용 검토.
- `UsStockDailyCandleService` (service): 종목 순회, factor 계산, upsert. `AdjustedCandleSyncService`(`src/service/adjusted_candle_sync_service.py`)를 참고 구현.
- 백필 스크립트 (`scripts/backfill_us_daily_candles.py`).
- 스케줄 잡 (일일 EOD).
- (선택) 워치리스트 시드 스크립트.

## 4. 스키마 변경

### 4.1 DataSource enum (`src/common/data_adapter.py`)
```python
FDR = ("fdr", TimeZone.NEW_YORK)
```
- `native_enum=False`(문자열 저장)라 **DB 마이그레이션 불필요**. KR이 일봉/수정주가를 `PYKRX` 하나로 묶듯, US도 `FDR` 하나가 내부 폴백 체인을 모두 덮는다.

### 4.2 tickers.exchange (마이그레이션 1건)
- `tickers`에 `exchange: Mapped[str | None]` nullable 컬럼 추가. US_STOCK은 `NAS/NYS/AMS`(KIS `dailyprice`의 EXCD) 저장, 그 외 자산은 NULL.
- 값은 등록 시 FDR `StockListing` 매핑(`NASDAQ→NAS, NYSE→NYS, AMEX→AMS`)으로 자동 채움. 주 소스 FDR/yfinance는 심볼만 필요하므로 exchange는 **KIS 폴백 전용**.

## 5. 데이터 흐름

### 5.0 종목 등록 (선행 필수)
1. 워치리스트 심볼(수십 개) 입력.
2. `UsStockTickerService`가 FDR `StockListing` 3종을 로드해 `심볼→(이름, 거래소)` 맵 구성.
3. 각 심볼 enrich 후 `TickerService.upsert` → `tickers`에 `US_STOCK / FDR / exchange` 등록.
4. 목록에서 못 찾은 심볼은 로그+skip(상장폐지·오타 등). 캔들 수집은 이 단계 이후에만 의미가 있다.

### 5.1 백필 (1회/수동 스크립트)
1. `find_by_data_source(DataSource.FDR)` (active=True) 로 대상 종목 조회.
2. 종목별 `fdr.DataReader(symbol, start='<가능한 최초>')` → 전체 히스토리 1콜.
3. 정규화 → 원주가 `bulk_upsert`, factor로 `adj_*` 계산 → `update_adjusted`.
4. 종목 간 throttle(~0.5s)로 레이트림 회피. 종목별 독립 커밋(멱등).

### 5.2 일일 EOD (스케줄)
- 미국장 마감(16:00 ET) 이후 데이터 안정화를 고려해 **매일 07:00 KST**(서머타임 무관) 실행.
- 종목별 최근 ~5거래일 증분 조회 → upsert(멱등, 중복 무해).
- 휴장일/빈 응답은 info 로그 후 skip.
- `ENABLE_SCHEDULER` 등 기존 게이트 따름.

## 6. 수정주가 / 저장 매핑

| stock_daily_candles 컬럼 | 값 |
|---|---|
| open / high / low / close / volume | FDR 원주가 OHLCV |
| trade_value | NULL (FDR/yfinance 미제공 — 필요 시 KIS로 보완) |
| adj_open / adj_high / adj_low | OHLC × factor (factor = adj_close / close) |
| adj_close | Adj Close |
| adj_volume | NULL (또는 volume / factor — 선택, 기본 NULL) |

- factor 비례 역조정은 분할·배당을 정확히 반영한다.
- PK (date, ticker_id) 기준 upsert로 재실행 멱등.

## 7. 동적 워치리스트 관리

- 워치리스트 = `tickers` 테이블의 `asset_type=US_STOCK, data_source=FDR, active=True` 행. **별도 config 불필요.**
- **추가**: 심볼만 주면 `UsStockTickerService`가 FDR 목록으로 이름·거래소를 채워 등록 → 다음 스케줄 자동 픽업. (단건은 just-in-time 조회 + 목록 캐시 활용. `POST /tickers` 확장 또는 전용 등록 경로는 구현 시 확정)
- **중단/제외**: `active=False` 로 토글.
- 시드 스크립트는 최초 일괄 등록 편의용(선택).

## 8. 에러 처리 / 견고성

- **소스 폴백 체인**: FDR 실패 → yfinance → KIS `dailyprice`(exchange 필요) → 로그+skip. 한 소스 실패가 종목을 막지 않음.
- **종목별 독립 session_scope + 커밋**: 한 종목 실패가 배치 전체를 막지 않고, 부분 성공/재실행이 안전.
- 빈/휴장 응답·부분 히스토리(소스가 못 주는 과거 구간) 허용.
- 종목 간 throttle로 비공식 소스(FDR/yfinance) 레이트림·차단 회피.

## 9. 테스트 (CLAUDE.md: 핵심만, 구현의 2배 이하)

- **Integration 1개(핵심)**: `UsStockDailyCandleService`에 mock FDR DataFrame 주입 → `stock_daily_candles`에 원주가 OHLCV + 올바른 `adj_*`(factor 계산 포함) upsert 검증.
- 추가 예외(최소): ① 빈 응답 skip, ② FDR 실패 시 yfinance 폴백, ③ `UsStockTickerService`가 mock StockListing으로 심볼→이름·거래소를 올바로 채워 등록(목록에 없는 심볼 skip 포함).
- 실제 네트워크 호출은 mock 처리.

## 10. 범위 밖 (후속)

- 조회 API (기존 `/candles/kr-stock`의 US 일반화 등).
- KIS `dailyprice` 폴백의 거래대금으로 `trade_value` 보완.
- 분봉/실시간 수집(별도 설계).

## 11. 영향받는 파일 (예상)

- 변경: `src/common/data_adapter.py`(enum), `src/database/models.py`(exchange 컬럼), 신규 alembic 마이그레이션 1건, `src/scheduled_tasks/schedules.py`·`tasks.py`(잡 등록), `src/container.py`(DI 등록).
- 신규: `src/providers/us_stock_daily_client.py`, `src/service/us_stock_ticker_service.py`, `src/service/us_stock_daily_candle_service.py`, `scripts/backfill_us_daily_candles.py`, (선택) 종목 등록 스크립트/엔드포인트, 테스트.
