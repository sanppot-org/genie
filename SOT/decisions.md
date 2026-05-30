의사결정 기록

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