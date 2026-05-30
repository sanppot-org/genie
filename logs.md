# 버그/이슈 해결 기록

최신순 상단. 원인·해결·주의사항 3줄 요약.

## 2026-05-30: 스크리너 배당연속증가(`_calc_streak`) 정확성 결함 — codex·OMC critic 교차검증

- **누락 연도(gap)가 연속을 끊지 않음(HIGH)**: `dividend_service._calc_streak`이 정렬된 연도 **배열 인덱스**를 인접 비교해, 배당 중단 연도(dps<=0은 sync 미적재 → row 결측)가 있어도 그 양옆 연도를 "연속"으로 잘못 인정. 예: 2020·2021·2023만 있고 2022 중단 → streak=2(정답 0). → 비교 전 `years_desc[i] - years_desc[i+1] != 1`이면 break.
- **recency 앵커 부재(HIGH)**: cutoff는 미래/진행중 연도만 제거할 뿐, 최신 데이터 연도가 cutoff_year인지 미검사 → 수년 전 배당 끊긴 종목도 과거 행진으로 점수 획득. → `years_desc[0] != cutoff_year`면 0 반환. 분기배당(`is_quarterly_dividend_bulk`)·cutoff 5월 경계는 정상 확인.
- **주의(미수정·운영성)**: ① 과거 회계연도가 부분 백필되면 연간 dps 합 과소 → 허위 증감(전체 히스토리 백필 필요). ② `fiscal_year`는 KIS `divi_aplc_yymm`("배당기준연월", record 기준) — 12월 결산은 정상이나 비-12월 결산은 ±1 오귀속 가능. ③ KIS가 분기지급을 "중간"으로 주면 분기배당 미탐지. 회귀 테스트 추가(gap/stale), 충돌하던 기존 테스트는 명시적 `today`로 결정화.

## 2026-05-30: DART 자사주 소각 수집 — 파싱·결측·마이그레이션 이슈

- **소각 구조화 API 부재**: KIS에 자사주 소각 데이터 전무, DART에도 소각 전용 구조화 JSON 없음(OpenDartReader `event()` 미지원). → `list()`로 "주식소각결정" 공시 식별 후 `document()` 원문 정규식 파싱. 주의: 레이블(`소각할 주식의 종류와 수`/`소각예정금액`/`소각 예정일`/`이사회결의일`)은 일정하나 보장은 없음 → 파싱 실패는 raise 말고 WARN+skip, fixture(삼성 20250218800029) 회귀 테스트로 고정.
- **라벨 변형으로 파싱 실패(prod 백필 중 발견)**: 삼성 양식만으로 만든 정규식이 다수 종목 양식을 놓침. ① `이사회결의일(결정일)`(삼성) vs `이사회결의일`(다수, 괄호 없음) → resolution_date 정규식이 `(결정일)`을 필수로 봐 전체 파싱 실패. → `이사회결의일\s*(?:\(결정일\))?\s*(날짜)`로 선택적 처리. ② `발행주식 총수`(공백) vs `발행주식총수`(붙임)은 이미 `\s*`로 무관. 주의: 변형 양식(나무가 190510 등) 회귀 테스트 추가. 실패 문서 4건 재파싱 정상 확인 후 prod 백필 재개.
- **결측 vs 진짜 0(스크리너 점수)**: ③ 자사주 보유 "없음→5점"의 "없음"은 0주(데이터 존재)임. `stock_treasury_stocks` row 자체가 없는 미백필 종목을 5점 주면 최고점 오류 → row 없음=0점+N/A로 처리(결측≠0주). PER/PBR 결측=0 정책과 일치.
- **alembic 015 `id` 컬럼 버그**: `Identity(always=True)` + `nullable=True` 동시 선언 → Postgres `conflicting NULL/NOT NULL`. → `nullable=False`로 수정(014와 동일). 주의: Identity는 NOT NULL 함의.
- **DART 초기 backfill 레이트리밋**: (선행) KIS와 달리 DART 분당 1,000건 여유 있으나, 소각은 종목당 list+공시별 document라 호출량 큼 → 증분 가드 + 백필/스케줄러 분리.
