# 리팩토링 기록

최신순 상단. 각 항목 3줄 요약 원칙(AS-IS/TO-BE, 삭제 라인 수, 성능/안전 지표).

## 2026-05-30: buyback/treasury sync 커밋 패턴 통일 + 죽은 코드 제거

- **AS-IS**: `BuybackSyncService`/`TreasuryStockSyncService`가 주입 repo의 세션에 `bulk_upsert`만 하고 커밋을 `@db_scoped`(스케줄러 런타임)에만 의존 → **standalone 백필 스크립트에선 커밋 주체 없음 → 롤백**(로그 upserted=N, 실제 0행). 또 전종목 DART 호출 동안 단일 트랜잭션 점유(idle-in-transaction 위험).
- **TO-BE**: 두 서비스를 `IncomeStatementSyncService` 패턴으로 통일 — `Database` 주입 + 짧은 `session_scope`로 티커 로드 + DART 호출은 트랜잭션 밖 + `session_scope`로 커밋. standalone/스케줄러 모두 정상 커밋(로컬 검증: buyback 28행·treasury 4행 영속).
- **죽은 코드 제거(D)**: `BuybackService.is_regular_buyback`(소비처 0 + 매입만 카운트해 "매입·소각" 스펙 불일치) → `ScreeningService` bulk 판정(매입 OR 소각)으로 대체. `src/service/buyback_service.py`(36줄) + `tests/service/test_buyback_service.py`(84줄) **삭제 = 120줄**.
- 검증: ruff/mypy 통과, pytest 826 passed.
