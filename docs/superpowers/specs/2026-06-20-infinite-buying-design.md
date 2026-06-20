# 무한매수법(라오어 매매법) 자동매매 — 설계 (큰틀)

- 작성일: 2026-06-20
- 상태: 큰틀 확정 / 디테일은 구현 계획 단계에서 보강
- 원전: `docs/무한매수법.md` (별지점·T·전반전/후반전·매수/매도 규칙의 단일 출처)

## 1. 목표와 범위

미국 레버리지 ETF(TQQQ, SOXL, KORU 등)에 대해 라오어 무한매수법을 **실주문 자동집행**한다. 매일 한국투자증권(KIS) API로 LOC/MOC/지정가 주문을 자동 제출하고, 체결을 받아 평단·T·사이클 상태를 자동 갱신한다. genie의 기존 자동매매 라인(변동성 돌파)과 동일한 선상에 올린다.

**범위 밖(이번 단계 아님):** 백테스트/시뮬레이션, 수동 어드바이저 모드.

## 2. 핵심 설계 결정

| 결정 | 선택 | 이유 |
| --- | --- | --- |
| 실행 범위 | 실주문 자동집행 | genie 자동매매 라인에 정식 편입 |
| 상태의 진실의 근원 | **자체 원장(ledger)** | 전략별 완전 격리, 정확한 사이클 추적. 평단·보유·누적액을 우리가 직접 계산·영속화 |
| 주기 | **1일 2회 fire-and-forget** | LOC/MOC 종가 체결 구조와 일치. 발주(마감 직전)→대조(마감 후) 분리, 장중 미관여 |
| 구조 | **순수 코어 + IO 어댑터 (헥사고날)** | 라오어 공식을 KIS·DB 없이 단위테스트로 검증. 돈이 걸린 공식 정확성이 생명 |
| 전략 패턴 | 기존 `BaseStrategy[T]`와 **분리된 독립 모듈** | `BaseStrategy`는 즉시 체결 암호화폐 1분봉용. LOC/MOC + 다일 체결 대조 + 원장과 안 맞음 |

## 3. 모듈 구조 & 책임 경계

```
src/infinite_buying/
├── domain/                      # 순수 코어 (KIS·DB 의존 0, 전부 단위테스트)
│   ├── separation_point.py      #   별지점 계산: 평단·T·base·분할 → 별지점
│   ├── progress.py              #   T 계산, 전반전/후반전 판정 (T vs 분할/2)
│   ├── per_round_amount.py      #   회당금액 갱신: 단리/반복리/복리
│   ├── order_plan.py            #   하루치 주문계획 산출 (매수/매도 단 구성)
│   └── cycle.py                 #   사이클 종료/신규 진입(첫 매수) 판정
│
├── model.py                     # DB 모델 (포지션상태 / 주문 / 설정)
├── repository.py                # 원장 영속화 (SQLAlchemy)
├── kis_adapter.py               # IO: HantuOverseasAPI 래핑 (발주·체결조회)
├── service.py                   # 오케스트레이션 (place_daily_orders / reconcile_fills)
└── config.py                    # 설정 로딩
```

**경계 원칙:** `domain/`은 입력값(평단·보유수량·T·회당금액·전일종가·config)을 받아 **숫자·주문계획만 반환**하는 순수 함수 모음. KIS·DB를 전혀 모른다. IO 조율은 오직 `service.py`가 담당(상태 읽기 → 코어 호출 → 발주/저장).

## 4. 데이터 흐름 (1일 2회)

### 발주잡 — 미국장 마감 직전 (LOC 주문 가능 시간대)
1. `repository`: 종목별 포지션상태 로드(평단, 보유수량, 회당금액, T, 사이클#)
2. `data`: 전일 종가 로드 (기존 us_stock_daily 캔들 재사용)
3. `domain.order_plan`: 상태 + config → 하루치 주문계획 생성
   - 보유 0 & 사이클 시작 → 첫매수(전일종가×1.1~1.15 LOC + 여유매수 단)
   - 전반전(T<분할/2) → 별지점매수(½) + 평단매수(나머지) [LOC]
   - 후반전(T≥분할/2) → 별지점매수(전액) + 여유매수 [LOC]
   - 매도: 쿼터매도(잔량 25% 별지점 LOC) + 지정가매도(잔량 75% 평단+15~20% AFTER 지정가)
   - 회차 소진 → 쿼터매도(MOC)만, 매수 X
4. `kis_adapter`: 계획대로 LOC/MOC/지정가 발주
5. `repository`: 발주한 주문을 '주문 원장'에 `PENDING` 기록(KIS 주문번호 포함)

### 대조잡 — 장 마감 후 / 다음날 아침
1. `kis_adapter`: KIS 체결조회(전일 발주분)
2. `repository`: 주문 원장과 대조 → 각 주문 `FILLED`/`UNFILLED` 마킹
3. `domain`: 체결 반영해 평단·보유수량·매수누적액 재계산
   - 매수 체결 → 평단·보유·누적액↑, 회당금액 갱신(반복리/복리), T↑
   - 쿼터매도 체결 → 보유·누적액 약 25%↓, T≈0.75배
   - 지정가매도 전량 체결 → 사이클 종료 → 사이클# +1, 상태 리셋(다음 발주잡서 첫매수)
4. `repository`: 갱신된 포지션상태 저장 + 실현손익 기록

**불변식:** 상태 변경(평단·보유·T·사이클)은 **오직 대조잡에서만** 발생한다. 발주잡은 "계획→주문→PENDING 기록"만 한다. → 멱등성·장애 복구 단순화.

## 5. DB 모델 (자체 원장)

```
infinite_buying_position    # 종목별 현재 상태 (사이클당 1행, 진실의 근원)
  ticker_id, cycle_no
  avg_price                 # 평단
  holding_qty               # 보유수량
  cumulative_buy            # 매수누적액
  per_round_amount          # 현재 회당금액 (반복리/복리로 갱신)
  phase                     # 전반전/후반전 (T로 파생, 조회용 캐시)
  status                    # ACTIVE / CLOSED
  realized_pnl              # 사이클 누적 실현손익

infinite_buying_order       # 발주 원장 (발주잡 기록, 대조잡 갱신)
  position_id, kis_order_no
  side                      # BUY / SELL
  order_kind                # 첫매수/별지점매수/평단매수/여유/쿼터매도/지정가매도
  order_division            # LOC / MOC / LIMIT(AFTER 지정가)
  target_price, qty
  status                    # PENDING / FILLED / UNFILLED / CANCELED
  filled_qty, filled_price, trade_date

infinite_buying_config      # 종목별 파라미터 (DB 테이블)
  ticker_id
  division                  # 분할수 (기본 40)
  base_gap                  # 종목별 최대 괴리율 (TQQQ=15, SOXL=20)
  allocation                # 할당금액
  compounding               # 단리 / 반복리 / 복리
  sell_limit_pct            # 지정가매도 % (TQQQ=15, SOXL=20)
  active
```

- **T는 저장하지 않는다.** `cumulative_buy / per_round_amount`로 매번 파생 → 원장 단일근원 유지.
- `phase`는 조회 편의용 캐시(T에서 파생).

## 6. 스케줄 & 설정

- **스케줄:** 기존 `src/scheduled_tasks/schedules.py`에 잡 2개 추가(발주/대조). 미국 서머타임 대응을 위해 ET 기준 트리거. `run_strategies`(1분 크립토)와 완전 분리.
- **설정:** `infinite_buying_config`를 **DB 테이블**로 운영, API/UI로 종목 추가·파라미터 조정(genie의 기존 ticker/strategy 관리 방식과 일관). 분할·할당·복리모드가 운영 중 변경될 수 있어 코드 상수보다 DB가 적합.

## 7. 재사용 자산 (genie 기존)

- 미국주식 주문: `HantuOverseasAPI` — LOC(`34`)·MOC(`33`)·LIMIT(`00`) 이미 지원
- 전일 종가: `UsStockDailyCandleService` / `stock_daily_candles` 테이블
- 의존성 주입: `src/container.py` (`dependency_injector`)
- 마이그레이션: alembic

## 8. 테스트 전략

genie TDD 가이드라인(핵심 비즈니스 로직에만, Integration 1개 지향)에 따라 `domain/` 순수 함수에 집중:
- 별지점 공식 검산(T=0 → 평단×(1+base%), T=분할/2 → 평단)
- 회당금액 갱신(단리/반복리/복리)
- 전반전/후반전 주문 수량 산출
- 사이클 종료/재시작 판정
- 체결 반영 후 평단·T 재계산
- `service` 레벨은 KIS/DB 목으로 발주잡·대조잡 통합 1개

## 9. 미해결(구현 계획에서 확정)

- KIS 미국주식 LOC/AFTER 지정가 **정확한 주문 가능 시간대·주간거래 제약** (리서치 필요)
- KIS 체결조회 API 응답 명세 및 부분체결 처리
- 전략 전용 계좌 분리 여부(전략 외 보유분 혼입 방지)
- 첫매수 "여유매수" 단 수 산정 규칙의 일반화
- LOC 종가 체결로 인한 예산 미소진분 처리(여유매수 추가 단)
