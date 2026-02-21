# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

`genie`는 FastAPI 기반의 멀티 거래소 자동매매 시스템입니다. Upbit, 한국투자증권(한투), Bithumb, Binance를 지원하며, 변동성 돌파 전략 등 자동매매 전략 실행, 백테스팅, 캔들 데이터 수집/저장, REST API를 제공합니다. TDD 방식으로 개발되며, Pydantic을 통한 타입 안전성을 보장합니다.

## 주요 기능

- **자동매매 전략 실행**: 변동성 돌파 전략 등 스케줄 기반 자동매매
- **멀티 거래소 지원**: Upbit, 한국투자증권, Bithumb, Binance
- **캔들 데이터 수집/저장**: TimescaleDB 기반 시계열 데이터 관리
- **백테스팅 엔진**: backtrader 기반, 다양한 전략 검증
- **REST API**: FastAPI 기반 전략 실행/조회, 캔들/티커 관리 API
- **스케줄링**: APScheduler 기반 자동 전략 실행 및 데이터 수집
- **알림/리포팅**: Slack 웹훅 알림, Google Sheets 거래 기록
- **DI 컨테이너**: dependency-injector 기반 의존성 관리
- **헬스체크**: Healthchecks.io 연동 시스템 모니터링
- **로깅**: Better Stack (Logtail) 원격 로깅

## 코드 구조

```
src/
├── config.py                        # 설정 클래스 (Upbit, Hantu, Bithumb, DB, Slack, Google Sheet 등)
├── constants.py                     # 상수 정의
├── container.py                     # DI 컨테이너 (dependency-injector)
├── logging_config.py                # Better Stack 로깅 설정
├── scheduler_config.py              # APScheduler 설정
├── allocation_manager.py            # 자산 배분 관리
├── api/                             # FastAPI REST API
│   ├── lifespan.py                  # 앱 lifecycle (스케줄러 시작/종료)
│   ├── schemas.py                   # API 스키마
│   ├── exception_handlers.py        # 예외 핸들러
│   └── routes/                      # API 라우터
│       ├── health.py                # 헬스체크 엔드포인트
│       ├── strategy.py              # 전략 실행/조회 API
│       ├── ticker.py                # 티커 관리 API
│       └── candle.py                # 캔들 데이터 API
├── strategy/                        # 자동매매 전략
│   ├── base_strategy.py             # 전략 기본 클래스
│   ├── volatility_strategy.py       # 변동성 돌파 전략
│   ├── strategy_context.py          # 전략 컨텍스트
│   ├── config.py                    # 전략 설정
│   ├── factory.py                   # 전략 팩토리
│   ├── order/                       # 주문 실행
│   │   ├── order_executor.py        # 주문 실행기
│   │   └── execution_result.py      # 실행 결과 모델
│   ├── cache/                       # 전략 캐시
│   │   ├── cache_manager.py
│   │   └── cache_models.py
│   └── data/                        # 전략 데이터
│       ├── models.py
│       └── collector.py
├── service/                         # 비즈니스 로직 서비스
│   ├── candle_service.py            # 캔들 저장 서비스
│   ├── candle_query_service.py      # 캔들 조회 서비스
│   ├── ticker_service.py            # 티커 서비스
│   └── exceptions.py                # 서비스 예외
├── database/                        # DB 레이어 (SQLAlchemy + TimescaleDB)
│   ├── database.py                  # DB 엔진/세션 관리
│   ├── models.py                    # SQLAlchemy 모델
│   ├── base_repository.py           # 베이스 리포지토리
│   ├── repositories.py              # 캔들 리포지토리
│   ├── candle_repositories.py       # 거래소별 캔들 리포지토리
│   └── ticker_repository.py         # 티커 리포지토리
├── upbit/                           # Upbit 거래소 API
│   ├── upbit_api.py
│   └── model/
├── hantu/                           # 한국투자증권 API
│   ├── base_api.py
│   ├── hantu_api.py
│   ├── domestic_api.py              # 국내 주식
│   ├── overseas_api.py              # 해외 주식
│   └── model/
│       ├── domestic/                # 국내 모델 (주문, 잔고, 차트 등)
│       └── overseas/                # 해외 모델 (가격, 주문, 잔고 등)
├── bithumb/                         # Bithumb 거래소 API
│   ├── bithumb_api.py
│   └── model/
├── providers/                       # 캔들 데이터 제공자
│   ├── upbit_candle_client.py
│   ├── hantu_candle_client.py
│   └── binance_candle_client.py
├── adapters/                        # 데이터 어댑터
│   ├── candle_adapters.py
│   └── adapter_factory.py
├── collector/                       # 데이터 수집기
│   ├── data_fetcher.py
│   └── price_data_collector.py
├── backtest/                        # 백테스팅 엔진
│   ├── backtest_builder.py          # 백테스트 빌더 패턴
│   ├── sizer_config.py
│   ├── commission_config.py
│   ├── data_feed/                   # 데이터 피드
│   │   ├── candle_loader.py
│   │   ├── pandas.py
│   │   └── base.py
│   ├── sizer/                       # 포지션 사이저
│   └── strategy/                    # 백테스트 전략들
│       ├── volatility_breakout_strategy.py
│       ├── ema_alignment_strategy.py
│       ├── ema_simple_alignment_strategy.py
│       ├── ema_dynamic_sizer.py
│       ├── morning_afternoon_strategy.py
│       ├── timed_hold_strategy.py
│       ├── split_strategy.py
│       ├── simple_strategy.py
│       └── buy_and_hold_strategy.py
├── common/                          # 공통 모듈
│   ├── candle_client.py             # 캔들 클라이언트 인터페이스
│   ├── candle_schema.py             # 캔들 스키마 (pandera)
│   ├── clock.py                     # 시간 유틸리티
│   ├── http_client.py               # HTTP 클라이언트
│   ├── data_adapter.py              # 데이터 어댑터 인터페이스
│   ├── order_direction.py           # 주문 방향 enum
│   ├── slack/                       # Slack 알림
│   │   ├── client.py
│   │   └── order_notification.py
│   ├── google_sheet/                # Google Sheets 연동
│   │   ├── client.py
│   │   ├── trade_record.py
│   │   └── cell_update.py
│   └── healthcheck/                 # 헬스체크 클라이언트
│       └── client.py
├── scheduled_tasks/                 # 스케줄 작업
│   ├── tasks.py                     # 작업 정의
│   ├── schedules.py                 # 스케줄 설정
│   └── context.py                   # 작업 컨텍스트
└── report/                          # 리포팅
    └── reporter.py

app.py                               # FastAPI 앱 엔트리포인트
alembic/                             # DB 마이그레이션
docker-compose.yml                   # TimescaleDB, pgAdmin
deploy.sh                            # 배포 스크립트 (롤백 포함)
genie.service                        # systemd 서비스 파일
.github/workflows/deploy.yml         # GitHub Actions CI/CD

tests/
├── test_config.py
├── test_container.py
├── test_constants.py
├── test_allocation_manager.py
├── api/                             # API 테스트
├── strategy/                        # 전략 테스트
│   ├── order/
│   └── data/
├── service/                         # 서비스 테스트
├── database/                        # DB 테스트
├── upbit/                           # Upbit 테스트
├── hantu/                           # 한투 테스트
│   └── model/
│       ├── domestic/
│       └── overseas/
├── bithumb/                         # Bithumb 테스트
├── providers/                       # 캔들 클라이언트 테스트
├── adapters/                        # 어댑터 테스트
├── backtest/                        # 백테스트 테스트
│   ├── data_feed/
│   ├── sizer/
│   └── strategy/
├── common/                          # 공통 모듈 테스트
│   ├── slack/
│   ├── google_sheet/
│   └── healthcheck/
├── scheduled_tasks/                 # 스케줄 작업 테스트
└── models/                          # 모델 테스트
```

## 개발 환경

### Python 환경

- Python 3.12+ 필요
- uv 패키지 매니저 사용

### 주요 의존성

**핵심 프레임워크**:
- `fastapi>=0.104.0`: REST API 프레임워크
- `uvicorn[standard]>=0.24.0`: ASGI 서버
- `pydantic>=2.12.3`: 데이터 모델 및 검증
- `pydantic-settings>=2.0.0`: 환경 변수 관리
- `dependency-injector>=4.48.2`: DI 컨테이너

**거래소 API**:
- `pyupbit>=0.2.34`: Upbit API 클라이언트
- `pyjwt>=2.10.1`: JWT 토큰 (한투 API 인증)
- `requests>=2.32.4`: HTTP 요청

**데이터베이스**:
- `sqlalchemy>=2.0.44`: ORM
- `psycopg2-binary>=2.9.11`: PostgreSQL 드라이버
- `alembic>=1.17.2`: DB 마이그레이션

**데이터 처리**:
- `pandas>=2.3.1`: 데이터 처리
- `pandera>=0.20.0`: DataFrame 스키마 검증
- `yfinance>=0.2.66`: Yahoo Finance 데이터
- `finance-datareader>=0.9.96`: 금융 데이터 리더

**백테스팅**:
- `backtrader>=1.9.78.123`: 백테스팅 엔진
- `matplotlib>=3.10.7`: 차트 시각화

**스케줄링/알림**:
- `apscheduler>=3.10.0`: 작업 스케줄러
- `gspread>=6.0.0`: Google Sheets API
- `tenacity>=9.0.0`: 재시도 로직
- `logtail-python>=0.2.0`: Better Stack 로깅

**코드 품질**:
- `ruff>=0.14.1`: 린터/포매터
- `mypy>=1.18.2`: 정적 타입 체크
- `pytest>=8.0.0`: 테스트 프레임워크

### 환경 설정

```bash
# 의존성 설치
uv sync

# 서버 실행
uv run uvicorn app:app --host 0.0.0.0 --port 8000

# 테스트 실행 (항상 uv 사용)
uv run pytest tests/

# 특정 테스트 실행
uv run pytest tests/upbit/test_upbit_api.py -v

# DB 마이그레이션
uv run alembic upgrade head

# 새 마이그레이션 생성
uv run alembic revision --autogenerate -m "설명"
```

### Git Submodule 관리

`config/` 디렉토리는 git submodule로 관리되며 민감한 설정 파일들을 포함합니다.

```bash
# 최초 클론 시 submodule 초기화
git submodule update --init --recursive

# submodule 업데이트
git submodule update --remote
```

## 인프라

### Docker Compose

TimescaleDB (PostgreSQL + 시계열 최적화)와 pgAdmin을 제공합니다.

```bash
# TimescaleDB 실행
docker-compose up -d timescaledb

# pgAdmin 포함 실행 (관리 UI)
docker-compose --profile admin up -d
```

### 배포

- **GitHub Actions**: 태그 푸시(`v*.*.*`) 시 자동 배포 (`.github/workflows/deploy.yml`)
- **배포 스크립트**: `deploy.sh` - uv sync, systemd 서비스 재시작, 실패 시 자동 롤백
- **systemd 서비스**: `genie.service` - `uv run uvicorn app:app --host 0.0.0.0 --port 8000`
- **배포 알림**: Slack 웹훅으로 배포 성공/실패 알림

### DB 마이그레이션

Alembic을 사용한 스키마 마이그레이션. `alembic/` 디렉토리에서 관리됩니다.

## 🏗️ 개발 가이드라인

### 🧪 전략적 TDD 가이드라인
- **최소주의:** 모든 함수에 테스트를 만들지 않는다. 핵심 비즈니스 로직과 복잡한 데이터 처리에만 집중한다.
- **Top-Down 접근:** 작은 단위 테스트(Unit) 수백 개보다, 주요 기능을 한 번에 검증하는 통합 테스트(Integration)를 지향한다.
- **테스트 생성 규칙:**
  1. 구현 전, 가장 핵심적인 성공 케이스 1개에 대한 테스트를 작성한다.
  2. 코드를 구현하고 테스트를 통과시킨다.
  3. 추가 테스트가 반드시 필요한 예외 상황인 경우에만 추가하되, 전체 테스트 코드가 구현 코드의 2배를 넘지 않도록 관리한다.
- **삭제 권한:** 기능 변경 시 의미가 퇴색되거나 중복된 테스트는 사용자 승인 없이 리팩토링 과정에서 과감히 병합하거나 제거하라.

### 📝 로그 기록 가이드 (SOT Logging)
작업이 완료되면 성격에 따라 아래 두 파일에 분리하여 기록하라.

1. **logs.md (사건/해결 중심):**
  - **언제:** 버그 발생 및 해결, 외부 API 이슈, 예상치 못한 동작 수정 시.
  - **내용:** 에러 메시지, 발생 원인, 해결 방법, 향후 주의사항.
  - **목적:** 동일한 기술적 시행착오와 삽질을 방지한다.

2. **refactor_logs.md (구조/최적화 중심):**
  - **언제:** 코드 중복 제거, 성능 최적화(백테스트 속도 등), 파일 분리, 불필요한 코드 삭제 시.
  - **내용:** AS-IS vs TO-BE, 리팩토링 사유, **삭제된 코드 라인 수**, 개선된 성능 지표.
  - **목적:** 시스템의 Lean함을 유지하고 기술 부채를 추적한다.

- **공통 규칙:** 모든 로그는 최신 항목이 상단에 오도록(Reverse-chronological) 작성하며, 3줄 요약을 원칙으로 한다.

### 🧠 시스템 지능 (SOT & Skills)
- **맥락 우선:** 작업 시작 전 반드시 `SOT/` 폴더를 읽어 최신 맥락을 파악하라.
- **기록 의무:** 새로운 결정은 `SOT/decisions.md`에, 작업 이력은 성격에 따라 `logs.md`와 `refactor_logs.md`에 기록하라.
- **로그 구분:**
  - `logs.md`: 버그, 에러 해결, API 이슈 등 '문제 해결' 기록.
  - `refactor_logs.md`: 중복 제거, 코드 삭제, 성능 최적화 등 '구조 개선' 기록.
- **수치화:** 리팩토링 후에는 반드시 **삭제한 코드 라인 수**를 명시하여 Lean함을 증명하라.

### 🛠️ 도구 및 맥락 관리 (OMC)
- **효율적 탐색:** 프로젝트 구조 파악 시 `omc`를 최우선으로 사용하되, 무분별하게 모든 파일을 읽지 말고 의존성이 높은 파일부터 단계적으로 탐색하여 토큰 낭비를 최소화하라.
- **수정 계획:** 코드 수정 전 반드시 수정 계획(Implementation Plan)을 요약하여 보고하고 사용자의 승인을 받아라.

### 🤖 에이전트 워크플로우
- **설계 우선 (Architect):** 신규 기능이나 대규모 리팩토링 전에는 반드시 `AGENTS/architect.md` 페르소나를 호출하여 설계안(위험 요소 및 대안 포함)을 먼저 작성하라.
- **코드 구현 (Developer):** 승인된 계획에 따라 코드를 작성하되, 항상 Lean한 상태를 유지하라.
- **자가 리뷰 (Reviewer):** 작업 완료 직후, `AGENTS/reviewer.md` 페르소나로 전환하여 방금 짠 코드를 스스로 비판하고 리팩토링 항목을 나열하라.

### 📈 자가 발전 규칙
- **SOT 최신화:** 작업 중 SOT에 명시되지 않은 중요한 사항이 생기면 사용자 확인 후 문서를 업데이트하라.
- **판단 기준:** 기존 인터페이스(Public API) 파괴나 외부 라이브러리 추가 시에는 반드시 명시적 승인이 필요하다. 그 외 로직 최적화는 자가 리뷰 후 보고만 수행한다.


### 코드 수정 후 체크리스트

1. 린트: `uv run ruff check src/`
2. 타입 체크: `uv run mypy src/`
3. 테스트: `uv run pytest tests/`
4. 빌드: `uv pip install -e .`

### 코드 품질 설정

**Ruff** (`pyproject.toml`):
- `line-length`: 180
- 활성화된 룰: `E`, `F`, `W`, `I`, `N`, `UP`, `ANN`, `B`, `A`, `C4`
- 테스트에서는 `ANN001`, `ANN201`, `ANN202`, `N802`, `F841`, `B017` 무시
- `src/backtest/`에서는 `ANN401` (Any 허용)

**MyPy** (`pyproject.toml`):
- `python_version`: 3.12
- `plugins`: `pydantic.mypy`
- backtrader, yfinance, FinanceDataReader, apscheduler, dependency_injector: `ignore_missing_imports`

## 보안 주의사항

### 민감 정보 관리

- **절대 API 키를 코드에 하드코딩하지 말것**
- `.env` 파일 또는 `config/` submodule에만 저장
- `.gitignore`에 `.env` 포함 확인

### config submodule 취급

- `config/` 디렉토리의 파일 내용을 외부에 노출하지 말것
- 모든 거래소 API 키, DB 비밀번호, Slack 웹훅 URL 등 특히 주의
- 테스트 시에도 실제 API 키 사용 최소화 (Mock 사용 권장)

### 환경 변수

`config/genie/.env`에서 관리 (프로필별 `.env.dev`, `.env.prod` 지원):

```bash
# Upbit
UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=

# 한국투자증권
CANO=
ACNT_PRDT_CD=
APP_KEY=
APP_SECRET=
URL_BASE=
TOKEN_PATH=
V_CANO=
V_ACNT_PRDT_CD=
V_APP_KEY=
V_APP_SECRET=
V_URL_BASE=
V_TOKEN_PATH=

# Bithumb
BITHUMB_ACCESS_KEY=
BITHUMB_SECRET_KEY=

# Database (TimescaleDB)
POSTGRES_DB=genie_trading
POSTGRES_USER=genie
POSTGRES_PASSWORD=
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Slack 웹훅
SLACK_WEBHOOK_URL_GENIE_LOG=
SLACK_WEBHOOK_URL_GENIE_DEBUG=
SLACK_WEBHOOK_URL_GENIE_STATUS=
SLACK_WEBHOOK_URL_REPORT=

# Google Sheets
GOOGLE_SHEET_URL=
GOOGLE_CREDENTIALS_PATH=config/auto-trade-google-key.json

# Healthcheck
HEALTHCHECK_URL=

# Better Stack (Logtail) 로깅
LOGTAIL_SOURCE_TOKEN=
LOGTAIL_SOURCE_HOST=

# App
ENABLE_SCHEDULER=true
ENV_PROFILE=dev
```

## 참고사항

- 설정 파일은 `config/` submodule을 통해 중앙 관리됩니다
- 테스트 실행 시 `uv run pytest tests/`를 사용해주세요