의사결정 기록

## 2026-06-04: 배당이력·BPS 액면분할 보정 (2e 후속)

### 배경
prod 실데이터 검증에서 2e(EPS·DPS 보정) 적용 후에도 분할 절벽이 남는 2곳 발견: ① 배당이력 차트(`stock_dividends`, 별도 소스 — 2e 미적용), ② BPS(주당순자산, `stock_fundamentals`). 삼성 FY2018 분기배당 17,700(분할 전)→354(분할 후), BPS 1,156,530(2017)→28,126(2018).

### 핵심 결정
- **배당이력**: `DividendService.get_history`가 캔들 주입받아 각 배당 `record_date` 시점 `factor=adj_close/close`로 DPS 환산(네이버 수정주가가 오늘 주식수로 back-adjust돼 있어 record_date factor가 곧 오늘 좌표계 보정). 반환 타입을 ORM `StockDividend`→`DividendHistoryPoint` 프로즌 dataclass(record_date/kind/dps/fiscal_year)로 변경(라우트는 `from_attributes`라 무변경). 캔들/adj_close 미존재·close≤0이면 factor=1.
- **BPS**: 2e와 동일 factor를 `_adjust_per_share_for_split`에서 곱함(eps·dps·bps 동일 factor → PBR=price/bps 비율 보존). 단 **데이터 계층만 보정** — 사용자 결정으로 API/프론트 미노출(`IncomeStatementPointData.bps`만 채움). 가드도 `bps is None` 포함하도록 확장.
- **스코어링**: `is_quarterly`는 kind만 검사라 무관. `_calc_streak`(연속배당인상)는 원본 DPS 연합산 비교라 **분할연도 판정 왜곡 잠재 버그**(FY2018 raw합 < FY2017 raw합) 존재.
  - 단건 `consecutive_dividend_increase_years`는 record_date factor로 DPS 환산 후 비교(보정 적용). `_calc_streak`는 StockDividend·DividendHistoryPoint 공용(fiscal_year·dps만 읽음, `_StreakRow` Union).
  - **screening 전종목 `_bulk`는 보정 미적용(의도)**: 교차검증(architect+code-reviewer)에서 bulk 보정안(분할후보 `find_split_candidate_ticker_ids` + 종목별 캔들 로드)이 **prod에서 캔들 11M행 전구간 윈도우 스캔으로 제한시간 초과**함을 실측 확인(배당 25,790건/2,003종목). screening마다 수초 회귀 → 되돌림. 분할은 드물어 영향 종목 소수 → 알려진 한계로 문서화. 효율적 보정(배당 record 지점 factor를 LATERAL 1쿼리)은 비용 대비 효용 낮아 보류.

### 검토
prod 읽기전용 재현: 배당 14건 전부 record_date factor 적용 정합(2018-03 17,700×0.02=354), BPS 1,156,530×0.02=23,130. 전체 922 passed(신규 3: 배당 분할/폴백, BPS 보정), ruff·mypy 클린.

### 알려진 한계 (2026-06-04): ~2014 이전 미보정
네이버 수정주가 일봉이 종목별 대체로 2014년(삼성 2014 중반)부터만 제공 → 그 이전 `adj_close` NULL이라 ① 차트 주가는 `price=adjusted`도 원주가 폴백, ② 재무 EPS·DPS·BPS도 factor 미적용(원본 유지) → 2013↔2014 경계 분할 절벽 잔존(삼성 2013 EPS 154,020·주가 1,372,000 원본; 2014 EPS 3,957·주가 26,540 보정). 해결안(가장 이른 adj factor f₀ 과거 역추정, 미커버 구간 분할은 원주가 밴드로 가드)은 사용자 판단으로 **보류**(효용 대비 복잡도·근사 오차 가능). 더 긴 수정주가 소스(FinanceDataReader 등) 전환은 별도 검토 대상. v1.34.0 배포 후 prod API 직접 검증으로 확인(`/api/candles?price=adjusted`·`/api/financials`·`/api/fundamentals`).

## 2026-06-03: 수정주가(adjusted) 차트 — 액면분할 절벽 제거 (Phase 1)

### 배경
삼성전자(005930) 장기 차트가 2018-05 50:1 액면분할로 265만원→5.3만원 절벽. 원인: 수집이 `get_market_ohlcv(market="ALL")` 일별 전종목 스냅샷 누적 → DB에 **원주가(분할 미보정)** 저장. 로그 스케일은 해결책 아님(분할은 비율변화가 아닌 레벨 점프).

### 핵심 결정
- **데이터 소스**: pykrx `get_market_ohlcv_by_date(ticker, adjusted=True)` = **네이버 금융**(원주가 KRX와 출처 다름). **KRX 인증 불필요**. 종목별·구간별 호출(bulk ALL은 수정주가 미지원). 네이버 일봉은 **~2014년부터** 제공.
- **모델**: 원주가(`open~close`, KRX) **불변 보존**, 수정주가는 **별도 컬럼** `adj_open/high/low/close/adj_volume`(alembic 017, nullable ADD COLUMN=잠금 최소). 분할 이벤트 테이블/쿼리타임 보정(안 C)은 Phase 2.
- **백필**: `AdjustedCandleBackfillService` — 기존 (ticker_id, date) row의 `adj_*`만 UPDATE(원주가 미존재 과거는 fabricate 안 함). 거래정지(OHLV·거래량 0) row 스킵. 수동 API `POST /candles/kr-stock/backfill-adjusted?ticker=`.
- **조회**: API/서비스 `price=raw|adjusted` 파라미터. **기본 raw**(Public API 하위호환), 프론트가 명시적으로 adjusted 요청. adjusted는 row를 `AggregatedCandle`로 치환(adj NULL이면 원주가 폴백) → resample/스키마/프론트 무변경.
- **부수 버그 수정**: `income_statement_service._enrich_with_price`가 결산주가를 원종가로 매칭 → 분할 전 원종가가 PER/주가 추세에 혼입되던 왜곡. `adj_close` 우선으로 수정.
- **분리 불필요 근거**: `stock_daily_candles`는 표시 전용(소비처=차트 API + 재무표). 백테스트는 `CandleDaily`, 자동매매 전략은 Upbit 데이터 사용 → 이 테이블 미참조. 매매/표시 물리분리 불필요(원주가 보존만으로 충분).

### 검토
codex + architect 교차검증(로그스케일 기각·B안 합의), pykrx 데이터 레벨 검증(연봉 2014~2024 연속·0값 3건), 로컬 Postgres E2E(017 마이그레이션 → 005930 백필 830/830 → raw=adj 0불일치). 백엔드 899 + 신규 테스트, mypy/ruff/프론트 lint·build 통과.

### Phase 2a (완료, 2026-06-03): 전종목 백필 배치
codex + architect 교차검증 반영.
- **단일 `AdjustedCandleSyncService`(Database 주입)로 통합** — 기존 단건 `AdjustedCandleBackfillService` 흡수·삭제. 단건 `backfill_one`(API/스크립트 --ticker) + 배치 `sync`(스크립트) 공통 `_process_ticker`. 청크 경계=1종목(종목별 UPDATE 모델이라 종목 묶음 무의미), 종목당 독립 session_scope 커밋, 네이버 호출은 트랜잭션 밖 → 중단 후 재개·멱등.
- **`date.in_(수천)` 제거**: `update_adjusted_from_rows(rows, mapping)`로 find_by_ticker 1회 로드 + 메모리 매칭(IN 플래닝/재조회 비용 제거).
- **throttle_sec=0.3**: 네이버 비공식 endpoint 연속 ~2,800콜 차단 회피(최우선 운영 리스크).
- **only_stale**: `ticker_ids_with_adjusted()` 1쿼리 집계로 skip(재개용, "신규 분할 재보정 감지 아님" — 2b 담당).
- **부분 보정 가시성**: result에 `existing`/`partial`(updated<existing) + WARN 로깅 → 2014 이전 네이버 미커버 구간 모니터링.
- 오프라인 스크립트 `scripts/backfill_adjusted_candles.py`(--ticker/--only-stale/--throttle-sec, 독립 프로세스). 검증: backend 902 passed, dev E2E(배치 sync 005930 830행, partial 0).

### Phase 2b (완료, 2026-06-03): 분할 감지 자동 재보정
codex + architect 교차검증 반영.
- **별도 cron task `readjust_kr_stock_splits`**(일봉 sync 16:58 직후 **17:10** 평일) — 일봉 task에 인라인 금지(책임/실패알림 격리, 기존 sync task 골격 복제). `@db_scoped @inject` + service만 호출.
- **감지**: `find_split_candidate_ticker_ids(since)` — raw 종가가 직전 거래일 대비 밴드 밖(`<0.6` or `>1.7`, KR ±30% 초과 = 분할·병합·권리락·감자) 종목. LAG 윈도우 + buffer(since-10일)로 경계일 prev 보존, division 없이 곱셈 비교. **raw 기준**(adj는 back-adjust돼 절벽 제거됨→감지 불가). `stock_daily_candles`는 일반 테이블(하이퍼테이블 아님), 일일 1회·소범위라 date 인덱스 없이 seq-scan 허용.
- **재보정**: `readjust_recent_splits(lookback_days=10)` = 감지(자체 session_scope) → `sync(ticker_codes=[후보])` 재사용(전체 adj overwrite — 네이버 back-adjusted라 분할 시 과거 전체 변동). lookback=실행 누락 방어 마진. 거짓양성은 멱등 재백필이라 무해, 거짓음성은 안전망.
- **신규일 adj 별도 처리 없음**: 비분할 종목 신규일은 adj NULL→raw 폴백(계수1=정확). 일봉 bulk_upsert는 adj_* 미갱신(보존 확인).
- **세션 정합**: `Database.session_scope()`는 `self.SessionLocal()` 새 세션이라 `@db_scoped` request-scope 토큰과 독립 → task가 자체 session_scope 서비스 호출해도 안전(2a와 동형).
- 검증: backend 906 passed, mypy/ruff, dev PG E2E(윈도우 감지쿼리 동작, 005930 후보0=분할없음 정확).

### 안전망 (앱 스케줄러, 분기) — 2026-06-04 결정 변경
전종목 재백필 안전망을 **OS cron → 앱 스케줄러 인라인**으로 변경(사용자 결정). 근거:
git 단일 소스(schedules.py)·OS crontab 관리 불필요·타 sync 잡과 일관. 원래의 "장시간 executor 점유" 우려는 이 경우 실질적이지 않음 — ① 분기 1회 **03:00**(트레이딩 7~21시·타 sync 16~19시대와 무충돌), ② ThreadPoolExecutor(max_workers=5)에서 1워커만 점유(여분 4), ③ **종목당 독립 session_scope 커밋이라 커넥션을 churn**(1.5h 점유 아님)이므로 [[project_db_session_leak]] 풀 고갈 패턴과 무관.
- task `resync_all_adjusted_candles`(@db_scoped, `sync(only_stale=False)` 전수 overwrite), cron `month=1,4,7,10 day=1 03:00`.
- `ScheduleConfig`에 옵셔널 `misfire_grace_time` 추가 → 분기 잡은 **3600초**(03:00 재시작/부하로 인한 분기 누락 방지; job_defaults 60초로는 부족).
- 오프라인 스크립트 `scripts/backfill_adjusted_candles.py`는 수동/초기 백필용으로 유지.

### Phase 2d (완료, 2026-06-04): prod 배포 + 전종목 백필
v1.31.0 배포(017 마이그레이션 적용), 앱 서버(150.230.252.125, ecrick-app)에서 전종목 백필 — `targets=2772 failed=0 tickers_updated=2764 rows=6.34M partial=1601`(partial=2014 이전 네이버 미커버). 005930 2018 분할 경계 adj_close 연속 검증. v1.32.0 분기 안전망 배포. 인프라: DB host=140.245.67.107(arm-db), app host=150.230.252.125(키 oci-app.key). 백필은 app 서버에서 실행해야 함(local→prod WAN은 종목당 수천행 왕복으로 17h, app 내부망은 ~1.5h).

### Phase 2e (완료, 2026-06-04): 펀더멘털(EPS·DPS) 수정주가 보정
codex + architect 교차검증 반영.
- **문제**: 재무요약 EPS·DPS가 stock_fundamentals(pykrx) 각 날짜 주식수 기준이라 2018 50:1 분할에서 2017→2018 ~1/50 절벽(주가만 보정됐고 주당지표는 미보정).
- **해법**: `_adjust_per_share_for_split(points, funds, candles)` 신규 — 조회시점 계산(컬럼 추가 X). 분할계수=adj_close/close를 **fundamental 스냅샷 날짜의 캔들**에서 산출(period_end 별도 bisect 아님 — 분할 경계에서 fund날짜≠가격날짜면 엉뚱한 factor 곱해질 위험). eps·dps에 **동일 factor** 적용(배당성향·유보 비율 보존).
- **범위**: eps·dps만(point에 bps 없음). 절대금액(매출·영업이익·순이익)·per(저장 비율)·div(비율) 불변. 가드 `close>0 & adj_close not None else factor=1`(2014 이전 원값). 추정행은 보정 안 함(이후 append, base_eps factor≈1).
- **프론트 무변경**: PER=p.per 저장값, 배당성향=dps/eps, 유보=eps-dps 모두 factor에 정합. **dividend-chart는 별도 소스(StockDividend record_date)라 영향 없음**(2e 범위 밖, 배당이력 차트 절벽은 후속 과제로 남김).
- 검증: backend 919 passed, mypy/ruff, **prod 데이터 read-only 검증**(005930 EPS 2,526→3,159→5,997→6,461 연속). 미배포(커밋/배포 대기).
- 전제 기록: **adj_close는 액면분할·무상증자 등 주식수 변동 보정용이며 현금배당 total-return factor가 아님.**

### 미착수
프론트 수정주가/원주가·로그 스케일 토글. 배당이력 차트(dividend-chart) DPS 분할 보정. adj_volume은 네이버 소스라 KRX 원거래량과 차이(종가는 정확 일치, 표시 영향 경미).

## 2026-05-30: 자사주 소각 수집 + 스크리너 자사주 점수(3지표)

### 핵심 결정
- **출처**: 자사주 소각은 **KIS에 전무**(전체문서 엑셀까지 확인) → **DART 전용**. DART에 소각 구조화 JSON API 없음(OpenDartReader `event()` 미지원) → `list()`로 "주식소각결정" 공시 식별 → `document()` 원문 **정규식 파싱**(레이블 일정: 소각주식수·소각예정금액·소각예정일·이사회결의일). 삼성 005930 실측 검증.
- **스키마**: 신규 `stock_cancellation_events`(PK `(ticker_id, rcept_no)`, 보통주/종류주 분리 보존, `cancel_date`/`cancel_amount`/`acquisition_method`). 기존 `stock_buyback_events`에 `event_type="CANCELLATION"`으로 **합치지 않음**(period_start 의미오염·종류주 손실 회피). architect/codex 합의.
- **sync 안전**: `CancellationSyncService`는 손익계산서 패턴(Database 주입 + 청크 독립 `session_scope` + DART 호출은 트랜잭션 밖). backfill 1회 + 주1회 cron(월 19:30).
- **백필 커밋 버그 수정**: 기존 `BuybackSyncService`/`TreasuryStockSyncService`가 주입 repo만 쓰고 커밋 주체가 `@db_scoped`(스케줄러)에만 의존 → **standalone 백필 스크립트에서 커밋 안 됨**(로그는 upserted=N, 실제 0행). 두 서비스를 손익/소각과 동일한 `Database` 주입 + 내부 `session_scope` 패턴으로 통일(부수효과: 전종목 DART 호출 중 트랜잭션 점유 안티패턴도 제거).
- **스크리너 점수(45→65점)**: 점수표 자사주 3지표(매입·소각 7 / 연간 소각비율 8 / 보유비율 5)를 `ScreeningService`에 추가. 별도 시스템 X — 기존 score 파이프라인 확장(repo bulk 메서드 3개 직접 주입, `fundamental_repository` 주입과 일관).
  - **결측 vs 진짜 0(가장 중요)**: ③ "없음→5점"은 **자기주식 0주(데이터 존재)**. treasury row 자체가 없는 종목(미백필)은 **0점+raw None(N/A)** — 5점 오인 절대 금지. ② issued 미상도 0점+N/A.
  - ② "연간"=**직전 12개월 rolling, resolution_date 기준**(cancel_date는 nullable·무인덱스). ① 매입은 취득**결정** 공시(intent)로 근사, DISPOSAL 제외.
  - 신규 컬럼은 **표시+정렬만**(필터는 결측정책 충돌·UX 혼란으로 2차). 응답에 `max_score` 추가.
- **죽은 코드 제거(D)**: `BuybackService.is_regular_buyback`(소비처 없음 + 매입만 카운트해 "매입·소각" 스펙 불일치) → bulk 판정으로 대체, `buyback_service.py`/테스트 삭제.

### 검토
architect/critic + codex 교차검증 2회(소각 수집 설계, 스크리너 점수 설계). 로컬 Postgres 실데이터 엔드투엔드 검증(삼성 7/3/4, SK 7/8/2, `DISTINCT ON` 최신연도 선택 정상).

## 2026-05-29: KIS 손익계산서(매출·영업이익·순이익) 수집 + 상세화면 표시

### 핵심 결정
- **데이터 소스**: KIS `income-statement`(FHKST66430200). 실측으로 단위=**억원**, tr_cont 불필요(단일 호출 전체 이력), 미제공 필드는 **"99.99" sentinel**→None, 분기는 **연단위 누적합산** 확인(삼성 005930 공시값 대조 통과).
- **스키마**: `stock_income_statements`(자연 복합 PK `(ticker_id, period_type, stac_yymm)`, 금액 `Numeric(20,2)` 억원, 분기 원본 누적 저장). 단일분기 환산은 **조회 시점 파생**(저장 X) — 알고리즘 변경 시 재백필 불필요.
- **수집 전략**: eager — 수집 로직 → 백필 1회(`scripts/backfill_income_statements.py`, 독립 프로세스) → 주1회 cron(월 19:00). 증분 가드는 **분기·연간 둘 다 최신일 때만** skip.
- **세션 안전(중요)**: sync 서비스가 **청크(200건)마다 독립 `Database.session_scope()`를 소유**하고 KIS 호출 루프는 **DB 트랜잭션 밖**에서 수행 → prod idle-in-transaction/QueuePool 누수 회피. buyback/treasury(주입 repo 단일 트랜잭션) 패턴과 **의도적으로 다름**(되돌리지 말 것).
- **에러 정책**: provider는 API 오류(429/5xx, rt_cd≠0)를 **전파**(빈 응답과 구분) → sync가 `api_calls_failed`로 집계. 빈 리스트는 '정상이나 데이터 없음'만 의미.
- **연간 표시**: KIS 연간 시리즈 선두에 미마감 분기 행(예: 202603)이 섞여 옴 → 조회 시 **결산월(최빈월) 행만 채택**.
- **executor**: 전용 executor 미추가. 백필을 오프라인 스크립트로 분리하면 정상 cron은 기존 default executor(5워커)+staggered로 1분 트레이딩 잡 보호 충분.

### 검토
3자 설계 검토(architect/critic/codex) + 독립 code-reviewer 반영. HIGH(429/5xx swallow) 수정 완료.

## 2026-02-21: 테스트 코드 정리 기준 수립

### 배경
테스트 코드에서 중복, 레이어 혼합, 프레임워크 보장 기능 재검증, 극소 파일 등의 문제가 발견되어 정리를 수행함.

### 삭제/축소 판단 기준

1. **Conftest 중복 제거**: 동일한 DB fixture가 `database/conftest.py`와 `service/conftest.py`에 복사되어 있으면 `tests/conftest.py`(루트)로 통합한다.
2. **레이어 혼합 금지**: API 테스트 파일에 리포지토리 레벨 테스트가 섞여 있으면 제거한다. 각 레이어는 자기 테스트 파일에서만 검증한다.
3. **프레임워크 보장 테스트 제거**: Pydantic enum 값 검증, 모델 생성자 호출 후 동일값 assert, 필수 필드 누락 ValidationError 등 프레임워크가 이미 보장하는 기능은 테스트하지 않는다.
   - **유지 대상**: alias 직렬화, API 응답 파싱, 비즈니스 기본값 등 커스텀 로직이 포함된 경우
4. **극소 파일 병합/삭제**: 테스트 1~2개만 있는 파일은 관련 파일에 병합하거나, 다른 테스트에서 암묵적으로 검증되면 삭제한다.

### 결과
- 삭제된 파일 4개: `database/conftest.py`, `test_hantu_stock_price.py`, `test_ticker.py`, `test_database.py`, `test_constants.py`
- 축소된 파일 4개: `test_ticker_api.py`, `test_chart.py`, `test_hantu_order.py`, `test_price.py`
- 생성된 파일 1개: `tests/conftest.py`
- 총 약 490줄 삭제, 588개 테스트 전체 통과 확인