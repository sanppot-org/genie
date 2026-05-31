# 주식 데이터 수집

- 주식 데이터를 수집해서 DB에 저장한다.
- 한국 주식을 시작으로 추후에는 다른 시장(미국 등)이나 다른 자산(코인 등)을 추가할 수 있다.
- 일봉을 시작으로 추후에는 분봉도 추가한다. 

- **데이터소스**: pykrx를 이용해서 한국 주식 데이터를 요청. (추후 미국 등 외국 주식 데이터 수집 기능 추가 예정)
- 매일 종목 정보를 수집해서 DB에 저장. 새로 추가되거나 사라지는 경우가 있다.
- 매일 일봉 데이터를 수집해서 DB에 저장한다.

## 테이블 구조
- 종목 정보: tickers
  - id
  - ticker
  - name
  - asset_type: 구분. (주식, ETF, 코인 등)
  - active: 활성화 여부. (True, False)
  - data_source: 데이터 소스. (pykrx, yahoo finance 등)

## 화면
- 종목 목록 조회


## TODO
[x] tickers 테이블 고도화
  [x] name, active 컬럼 추가
  [x] data_source eunm에 PYKRX 추가
[x] pykrx 연동
  [x] pykrx 의존성 추가 (pyproject.toml + mypy override)
  [x] PykrxTickerClient 구현 (주식 + ETF 종목 코드/이름 조회)
  [x] 단위 테스트 (mock)
[x] 종목 정보 데이터 수집
  [x] PykrxTickerInfo → Ticker 엔티티 변환 로직
  [x] 신규 종목 INSERT
  [x] 사라진 종목 active=False (soft-delete)
  [x] 이름이 변경된 경우 name 업데이트
  [x] 재상장 시 active=True 복구
  [x] active 보존을 위한 동기화 전용 서비스 메서드 (TickerCreate 우회)
  [x] 통합 테스트 (인메모리 DB)
[x] 한국 주식 수동 동기화 API (POST /api/tickers/sync/kr-stock)
[x] 종목 정보 수집 스케줄러 구현
  [x] APScheduler 작업 등록 (장 마감 후 1회, 예: KST 16:48)
  [x] 휴장일 가드 (주말/공휴일에 호출 skip)
  [x] 실패 시 Slack 알림

[x] OpenDartReader 연동 — 업종 메타데이터 보강 (1차)
  [x] OpenDART 인증키 발급 후 `config/genie/.env`에 `DART_API_KEY` 추가
  [x] `opendartreader` 의존성 추가 (pyproject.toml + mypy override)
  [x] `tickers.industry_code` 컬럼 추가 (alembic migration 006, nullable)
  [x] KSIC 코드 → 업종명 정적 매핑 (`src/common/ksic.py` + `industry_name_of` 헬퍼)
  [x] `DartCompanyClient` 구현 — `fetch_company_info(stock_code) -> DartCompanyInfo | None`, tenacity 재시도
  [x] DI 컨테이너에 client 등록 + `TickerSyncService`에 주입
  [x] sync 로직 확장 — 신규 ticker INSERT 시점에만 DART 조회 (best-effort, 실패 시 컬럼 None)
  [x] 단위/통합 테스트 (DartCompanyClient mock, sync 성공/실패 케이스, KSIC 매핑)

[ ] 종목 펀더멘털 데이터 수집 — `pykrx.stock.get_market_fundamental`
  - **목표**: 일자별 BPS/PER/PBR/EPS/DIV/DPS 시계열 적재 (밸류에이션·스크리닝·백테스팅 입력용)
  - **수집 방식**: `get_market_fundamental(date, market="ALL")` 1회 호출로 전 종목 일괄 조회 (per-ticker 루프 X)
  - **대상**: KR_STOCK만 (ETF는 펀드라 PER/PBR 등 의미 없음 → 응답에 섞여 있어도 ticker 매칭 시 자연히 제외됨)
  - **빈 응답 가드**: 휴장일이 아닌데 비어 있으면 `PykrxTickerClient`와 동일하게 `EmptyPykrxResponseError` 재시도

  [x] 테이블 추가: `stock_fundamentals`
    - 컬럼: `id`(BigInteger Identity), `ticker_id`(Integer FK → tickers.id), `date`, `bps/per/pbr/eps/div/dps`(Float, nullable), `created_at/updated_at`
    - 수치형: `Float` (코드베이스 컨벤션 — candle도 Float 사용)
    - PK: `(date, ticker_id)` — 멱등 UPSERT 키 (CandleDaily와 동일 패턴)
    - Index: `(ticker_id, date)` — 종목별 시계열 조회용 (date 단독 인덱스는 PK 첫 컬럼이라 불필요)
  [x] Alembic migration 007 (`007_add_stock_fundamentals_table.py`)
  [x] `src/database/models.py`에 `StockFundamental` 모델 + `src/database/stock_fundamental_repository.py` (bulk_upsert, find_by_ticker, find_by_date) + DI 등록
  [x] `PykrxFundamentalClient` 구현 (`src/providers/pykrx_fundamental_client.py`) — `fetch_by_date(date)`, tenacity 재시도, NaN→None 정규화, `EmptyPykrxResponseError` 재사용
  [x] `FundamentalSyncService.sync(date)` — bulk fetch → KR_STOCK ticker 매핑 → bulk_upsert (트랜잭션 1회 commit)
    - pykrx 티커 → `tickers.id` 매핑: `find_by_data_source(PYKRX)` 로드 후 in-memory dict (KR_STOCK만 포함, ETF/ETN 자연 제외)
    - 미매핑 코드(신규상장 등)는 `skipped_unmapped`로 집계
  [x] DI 컨테이너 등록 (`pykrx_fundamental_client` Singleton + `fundamental_sync_service` Factory)
  [x] 수동 동기화 API: `POST /api/fundamentals/sync/kr-stock?date=YYYYMMDD` (date 생략 시 오늘 KST)
  [x] 스케줄러 등록 — `sync_kr_stock_fundamentals` cron 17:00 mon-fri (티커 동기화 16:48 + 12분 여유)
  [x] 휴장일/빈응답 처리 + Slack 실패 알림 — `EmptyPykrxResponseError`는 info log only (휴장일 추정), 그 외 예외만 Slack
  [x] 백필 스크립트 — `scripts/backfill_fundamentals.py` (`--start --end YYYYMMDD`, 휴장일·실패 일자별 분류)
  [x] 테스트
    - PykrxFundamentalClient: bulk 응답 파싱, 빈 응답 재시도, NaN 정규화 (3 케이스)
    - FundamentalSyncService: 신규 + ETF skip, 미매핑 skip, 멱등성 (3 케이스, 인메모리 SQLite)
    - 스케줄 task 분기 (정상/휴장/예외→Slack) — 3 케이스

[x] 주가 데이터(일봉) 수집 — `pykrx.stock.get_market_ohlcv`
  - **목표**: 일자별 OHLCV+거래대금 시계열 적재 (차트·백테스팅 입력용)
  - **수집 방식**: `get_market_ohlcv(date, market="ALL")` 1회 호출로 전 종목 일괄 (per-ticker 루프 X)
  - **대상**: KR_STOCK만 (ETF 자연 제외), 거래정지(volume=0) skip
  - **저장소 분리**: 기존 `candle_daily`는 1분봉 집계 view라 INSERT 불가 → 별도 `stock_daily_candles` 테이블

  [x] 테이블 `stock_daily_candles` (alembic 008, PK `(date, ticker_id)`, FK tickers, idx `(ticker_id, date)`)
  [x] `StockDailyCandle` 모델 + `StockDailyCandleRepository` (bulk_upsert / find_by_ticker / find_by_date) + DI
  [x] `PykrxDailyCandleClient` (`fetch_by_date`, tenacity 재시도, 휴장일/빈응답 가드, 거래대금 nullable)
  [x] `DailyCandleSyncService.sync(date)` — bulk fetch → KR_STOCK 매핑 → bulk_upsert 1트랜잭션
  [x] 수동 동기화 API `POST /api/candles/sync/kr-stock?date=YYYYMMDD` (생략 시 오늘 KST)
  [x] 백필 스크립트 `scripts/backfill_daily_candles.py` (`--start --end YYYYMMDD`, 휴장일·실패 일자별 분류)
  [x] 테스트 — `DailyCandleSyncService` 3케이스(매핑/미매핑/no_trade, 휴장일 전파, 멱등) + API 2케이스
  [x] 스케줄러 등록 — `sync_kr_stock_daily_candles` cron 17:10 mon-fri (ticker 16:48 → fundamental 17:00 → 일봉 17:10)

[ ] 액면분할 후 주가
[x] 로컬에서 better stack 비활성화
[x] 프로파일에 따라서 스케줄러 비활성화
[x] 재무제표에 eps, per 추가 — 손익계산서 표에 EPS·PER 컬럼(결산말일 펀더멘털 스냅샷, 신규 수집 없이 stock_fundamentals 재사용)
[x] 손익계산서 표에 주가 컬럼 — 결산말일 일봉 종가 스냅샷(stock_daily_candles bisect, 적자기업도 값 존재)
[x] 손익계산서 차트 영업이익, 순이익 가독성 높이기
[x] 예상 이익(컨센서스 추정실적) 추가 — 손익계산서 표에 2026E/2027E 행(KIS estimate_perform 온디맨드, 연간뷰만, 매출·영업이익·순이익·EPS·PER). 미커버 종목은 표시 안 함, 확정연도 매출 대조 안전가드, 차트는 확정만
[ ] 종목 선정 점수표 고도화
  [ ] 중복 상장 여부
  [ ] 이익 지속 가능성
  [ ] 미래 성장 잠재력
  [ ] 기업 경영
  [ ] 세계적 브랜드 보유 여부

[ ] 스크리닝
  [ ] 다중 정렬
  [ ] 필터링
    [x] 복합
    [x] 종목 검색
    [x] 분기, 연속, 총점
  [x] 지표에 마우스 올리면 점수 공식 보이기
  [x] 자사주 점수 3지표 추가 (매입·소각 7 / 연간 소각비율 8 / 보유비율 5) — 45→65점, 표시+정렬(필터는 2차), 결측은 N/A·0점
  [ ] 업종 컬럼 추가
[] 종목 상세
  [x] 가장 최근 종목을 기본값으로 설정
  [ ] 차트
    [x] per (on/off)
    [x] pbr (on/off)
    [x] 시가배당율 (on/off)
    [x] 차트 우측에서 스크롤 시 세로로 길이 조절
  [x] 배당 내역
    [x] 기간 조절
  [x] 손익계산서 (매출·영업이익·순이익) — KIS income-statement
    [x] 막대그래프 3계열 + 요약 표(YoY·영업이익률·순이익률)
    [x] 연간/분기 토글 + 분기 단일환산 토글

[x] 손익계산서 수집 (KIS income-statement) — `stock_income_statements`, 백필 스크립트 + 주1회 스케줄러(월 19:00), 증분 가드, 청크 커밋
[x] 자사주 소각 수집 (DART 자기주식소각결정 공시) — `stock_cancellation_events`(보통/종류주 분리), `list`+`document` 정규식 파싱, 백필 스크립트 + 주1회 스케줄러(월 19:30), 청크 커밋
[x] buyback/treasury sync 백필 커밋 버그 수정 — `Database` 주입 + 내부 `session_scope`로 통일(standalone 백필도 커밋되도록), 죽은 `BuybackService` 제거
[x] 업종/섹터 데이터 추가 (KIS) 기존 데이터 교체 (스케줄러)
[x] 배당 종류 중간 / 반기 / 분기 합치기 — sync 시 (ticker_id, record_date, dps) 그룹은 QUARTERLY>INTERIM>SETTLE 1건만 적재, 기존 데이터는 `scripts/cleanup_dividend_duplicates.py`로 정리

## 추후 작업
- 동기화 작업 결과를 DB에 기록 (성공/실패/skip + SyncResult 카운트). 운영 가시성 및 통계용. 스케줄러가 안정화된 후 진행.
- 펀더멘털 데이터 활용: 섹터(industry_code) × PER/PBR 평균, 저평가 스크리닝 API
- 분기/연간 재무제표 — 매출·영업이익·순이익은 KIS income-statement로 완료(위 참조). TTM PER 등 추가 항목은 DART OpenAPI `finstate` 또는 KIS 재무비율 보강 검토.