의사결정 기록

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