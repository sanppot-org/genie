# CLAUDE.md

## 프로젝트 개요

`genie`는 FastAPI 기반 멀티 거래소(Upbit, 한국투자증권, Bithumb, Binance) 자동매매 시스템. 
변동성 돌파 등 전략 실행, 백테스팅(backtrader), 캔들 수집/저장(TimescaleDB), REST API 제공. Python 3.12+, uv, Pydantic, SQLAlchemy, APScheduler 기반.

프론트엔드는 `web/` 디렉토리에 분리 (Next.js 16 + React 19 + Tailwind v4 + shadcn/ui + TanStack Query, pnpm). FastAPI 백엔드의 JSON API를 소비하는 대시보드·차트(`lightweight-charts`, `recharts`) UI.

## 개발 명령어

```bash
uv sync                                      # 의존성 설치
uv run uvicorn app:app --host 0.0.0.0 --port 8000   # 서버 실행
uv run pytest tests/                         # 테스트 (항상 uv 사용)
uv run ruff check src/                       # 린트
uv run mypy src/                             # 타입 체크
uv run alembic upgrade head                  # 마이그레이션 적용
uv run alembic revision --autogenerate -m "설명"   # 새 마이그레이션
git submodule update --init --recursive      # config submodule 초기화

# 프론트엔드 (web/)
pnpm --dir web install                       # 의존성 설치
pnpm --dir web dev                           # 개발 서버 (http://localhost:3000)
pnpm --dir web build                         # 프로덕션 빌드
pnpm --dir web lint                          # ESLint
```

**코드 수정 후 체크리스트:** ruff → mypy → pytest 순서. (프론트엔드는 `pnpm --dir web lint` + `pnpm --dir web build`.)

## 개발 가이드라인

### TDD (전략적)
- 모든 함수가 아닌 **핵심 비즈니스 로직과 복잡한 데이터 처리**에만 테스트 작성.
- Unit 다수보다 Integration 1개를 지향.
- 절차: 핵심 성공 케이스 1개 → 구현 → 통과 → 꼭 필요한 예외만 추가. **테스트 코드는 구현 코드의 2배 이하**.
- 의미가 퇴색·중복된 테스트는 리팩토링 시 사용자 승인 없이 제거 가능.

### 로그 기록 (SOT)
- `logs.md`: 버그/에러/외부 API 이슈 해결 기록 (원인·해결·주의사항).
- `refactor_logs.md`: 구조 개선·중복 제거·성능 최적화 기록 (AS-IS/TO-BE, **삭제 라인 수**, 성능 지표).
- 공통: 최신순 상단, 3줄 요약 원칙.

### 시스템 지능 (SOT)
- 작업 시작 전 `SOT/` 폴더로 최신 맥락 파악.
- 새 결정은 `SOT/decisions.md`에 기록.
- SOT에 없는 중요 사항이 발견되면 사용자 확인 후 업데이트.

### 에이전트 워크플로우
- **Architect 우선:** 신규 기능·대규모 리팩토링 전 `AGENTS/architect.md` 페르소나로 설계안(위험·대안 포함) 작성.
- **Developer:** 승인된 계획대로 Lean하게 구현.
- **Reviewer 자가 리뷰:** 작업 직후 `AGENTS/reviewer.md` 페르소나로 자기 비판 및 리팩토링 항목 나열.
- **수정 계획 보고:** 코드 수정 전 Implementation Plan을 요약·승인받음.
- **승인 필요:** Public API 파괴, 외부 라이브러리 추가는 명시적 승인 필요. 그 외 로직 최적화는 자가 리뷰 후 보고.

## 코드 품질 설정

- **Ruff** (`pyproject.toml`): `line-length=180`, 룰 `E,F,W,I,N,UP,ANN,B,A,C4`. 테스트는 `ANN001/201/202, N802, F841, B017` 무시. `src/backtest/`는 `ANN401` 허용.
- **MyPy**: `python_version=3.12`, `plugins=pydantic.mypy`. backtrader, yfinance, FinanceDataReader, apscheduler, dependency_injector는 `ignore_missing_imports`.

## 인프라 / 배포

- **GitHub Actions**: `v*.*.*` 태그 푸시 시 자동 배포 (`.github/workflows/deploy.yml`).
- **deploy.sh**: uv sync → systemd 재시작, 실패 시 자동 롤백, Slack 알림.
- **systemd**: `genie.service` (`uv run uvicorn app:app ...`).
- **DB**: TimescaleDB (Docker Compose, `--profile admin`으로 pgAdmin 포함).
- [인프라 정보](./docs/infra.md)

## 보안

- API 키 하드코딩 금지. `.env` 또는 `config/` submodule에만 저장.
- `config/` 내용은 외부 노출 금지 (거래소 키, DB 비번, Slack 웹훅 등).
- 테스트에서도 실제 API 키 최소화, Mock 권장.
- 환경 변수는 `config/genie/.env` (프로필별 `.env.dev`, `.env.prod`)에서 관리. 주요 키: Upbit/한투/Bithumb 인증, TimescaleDB 접속정보, Slack 웹훅, Google Sheets, Healthcheck, Logtail, `ENABLE_SCHEDULER`, `ENV_PROFILE`.

## 작업규칙

- 커밋은 임의로 하지 말고 사용자의 허락을 구한다.
- **DB 쓰기 명령(특히 `alembic upgrade/downgrade`, `psql` 변경 쿼리) 실행 전에는 반드시 호스트를 먼저 확인하고 사용자 승인을 받는다.** `.env.dev`/`.env.prod`가 prod IP(`140.245.67.107` 등)를 가리킬 수 있어, 무심코 prod DB에 마이그레이션이 적용될 수 있다. 점검 순서: ① `uv run python -c "from src.config import DatabaseConfig; print(DatabaseConfig().database_url)"` 로 대상 확인 → ② 사용자에게 대상 명시하며 승인 요청 → ③ 실행. 로컬 docker 대상이면 `ENV_PROFILE=local` 또는 `POSTGRES_HOST=localhost`로 명시.
- 외부 API(KIS, PYKRX 등) 연동 시 API 요청과 응답에 대한 명세를 충분히 숙지하고 작업한다. 명세가 불충분한 경우 임의로 작업하지 말고 사용자에게 요청한다.