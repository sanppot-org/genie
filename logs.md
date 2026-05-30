# 버그/이슈 해결 기록

최신순 상단. 원인·해결·주의사항 3줄 요약.

## 2026-05-30: DART 자사주 소각 수집 — 파싱·결측·마이그레이션 이슈

- **소각 구조화 API 부재**: KIS에 자사주 소각 데이터 전무, DART에도 소각 전용 구조화 JSON 없음(OpenDartReader `event()` 미지원). → `list()`로 "주식소각결정" 공시 식별 후 `document()` 원문 정규식 파싱. 주의: 레이블(`소각할 주식의 종류와 수`/`소각예정금액`/`소각 예정일`/`이사회결의일`)은 일정하나 보장은 없음 → 파싱 실패는 raise 말고 WARN+skip, fixture(삼성 20250218800029) 회귀 테스트로 고정.
- **결측 vs 진짜 0(스크리너 점수)**: ③ 자사주 보유 "없음→5점"의 "없음"은 0주(데이터 존재)임. `stock_treasury_stocks` row 자체가 없는 미백필 종목을 5점 주면 최고점 오류 → row 없음=0점+N/A로 처리(결측≠0주). PER/PBR 결측=0 정책과 일치.
- **alembic 015 `id` 컬럼 버그**: `Identity(always=True)` + `nullable=True` 동시 선언 → Postgres `conflicting NULL/NOT NULL`. → `nullable=False`로 수정(014와 동일). 주의: Identity는 NOT NULL 함의.
- **DART 초기 backfill 레이트리밋**: (선행) KIS와 달리 DART 분당 1,000건 여유 있으나, 소각은 종목당 list+공시별 document라 호출량 큼 → 증분 가드 + 백필/스케줄러 분리.
