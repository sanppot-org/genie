# 프론트엔드 (데이터 분석/차트 뷰어)

genie 백엔드(FastAPI)에 붙는 데이터 분석·차트 뷰어용 SPA. 1차 목표는 **혼자 쓰는 분석 도구**, 향후 외부 공개 여지를 남긴다.

## 기술 스택

- **Next.js (App Router) + TypeScript** — React 기반 1순위, AI/예제 자료 풍부
- **TailwindCSS + shadcn/ui** — CSS 학습 부담 최소, 컴포넌트 복붙 방식
- **TanStack Query** — FastAPI fetch/캐시/로딩/에러 일괄 처리
- **Recharts** — 일반 차트 (라인/막대/스캐터)
- **TradingView Lightweight Charts** — 캔들 차트 (필요해질 때 도입)
- 패키지 매니저: `pnpm`

YAGNI로 **지금 도입 안 함**: 인증/로그인, SSR/SEO, 상태관리 라이브러리(Zustand 등), i18n, 다크모드 토글, Storybook, E2E 테스트.

## 디렉토리

```
genie/
├── (백엔드)
└── web/                       # 프론트 루트 (하위 폴더, monorepo 아님)
    ├── app/                   # Next.js App Router
    ├── components/            # shadcn + 자체 컴포넌트
    ├── lib/                   # api client, query 훅
    └── ...
```

## 화면 (1차)

- 종목 검색·목록
- 종목 상세: PER/PBR/BPS/EPS 시계열 차트
- 일봉 캔들 차트 (해당 종목)
- 섹터별 PER 분포 (스캐터 또는 박스플롯)

## TODO

### Phase 1. 셋업
[x] `web/` 폴더에 `create-next-app` 부트스트랩 (TS, Tailwind, App Router, ESLint)
[x] shadcn/ui 초기화 (`pnpm dlx shadcn@latest init -d --no-monorepo -y`)
[x] TanStack Query Provider 셋업 (`web/app/providers.tsx`)
[x] `lib/api.ts` 작성 (fetch wrapper, baseURL은 env로)
[x] FastAPI에 CORS 미들웨어 추가 (`CORS_ALLOW_ORIGINS` 환경변수, 기본 `http://localhost:3000`)
[x] `.env.local` (NEXT_PUBLIC_API_BASE_URL) + `.env.example`
[x] `web/README.md` 작성 (실행 방법, 구조, 스크립트)

### Phase 2. 차트 뷰어 MVP (심플 1차 — 단일 페이지 통합, 최근 1년 PER만)
[x] 읽기 전용 API 추가
  [x] `GET /api/fundamentals?ticker=&from=&to=` — 시계열 + 종목 미발견 시 404
  [x] `GET /api/tickers?q=&asset_type=&limit=` — ILIKE 검색, active=True 한정 (기존 GET /tickers 후방호환)
[x] 단일 페이지(`/`) — 검색창 + 결과 리스트 + 선택 시 아래에 PER 라인 차트 (최근 1년 고정)
[x] 인라인 Loading/Error/Empty 상태 (별도 컴포넌트 없이 텍스트)
[~] 라우팅 분리(`/stocks/[ticker]`), 기간 필터(1M/3M/1Y/ALL), Skeleton/Alert 컴포넌트화 — 보류 (추후 필요해지면 도입)

### Phase 3. 일봉 캔들 (심플 1차 — 단일 페이지 통합)
[x] `GET /api/candles/kr-stock?ticker=&from=&to=` 추가 (stock_daily_candles read, `GET /fundamentals` 미러)
[x] TradingView Lightweight Charts(v5) 도입 — `components/candle-chart.tsx` (`addSeries(CandlestickSeries)`, ssr:false)
[x] 단일 페이지 `/`에 PER 차트 아래 일봉 candlestick 섹션 추가 (최근 1년 고정, 한국식 색상)
[~] 캔들 + 거래량 동기화 표시 — 보류 (심플 우선, 추후)
[~] 종목 상세 페이지 라우팅 분리(`/stocks/[ticker]`) — 보류 (Phase 2와 동일 방침)

[ ] 종목 고도화
  [ ] 시가 배당률
  [ ] PER
  [ ] PBR
[ ] 차트 고도화
  [x] 기간 설정 — 차트 좌측 팬 시 과거 자동 확장(1Y→3Y→10Y→ALL). 차트 1회 생성·시간구간 보존
  [x] 거래량 추가 — 캔들 패인 하단 20% 반투명 히스토그램 오버레이(한국식 색, 전용 가격축 "vol")
  [x] 이평선 추가 — 5/20/60/120 SMA(종가 클라 계산, 캔들 오버레이) + MA별 on/off 버튼 토글
  [x] per 합치기 — lightweight-charts v5 멀티 페인. 캔들(pane 0) 아래 PER 라인(pane 1) 동기화, 주가:PER=3:1
[ ] 검색 창 고도화
  [x] 검색 목록 리스트는 검색창에 커서가 있을 때만 보이게하기 — onFocus/onBlur 게이트, 결과 클릭은 onMouseDown preventDefault로 보존
  [x] 검색창 연결형 드롭다운 (구글/네이버식) — relative 래퍼 + absolute 패널(콘텐츠 안 밀고 덮음, 그림자), 선택 시 닫힘(focus 해제)
[x] 최근 선택 종목 저장 (localStorage, 최대 8·dedupe) — 검색창 아래 칩 버튼 상시, 칩 ✕로 개별 삭제

## 배포

- 태그 `v*.*.*` push → GitHub Actions가 `web/`을 정적 export(`output: 'export'`) 빌드 → `out/`을 서버 `/var/www/genie/`로 scp → 백엔드 `deploy.sh` 실행
- nginx가 `/`는 정적 파일 서빙, `/api/*`는 `127.0.0.1:8000`(uvicorn) reverse proxy → **same-origin**이라 CORS 불필요
- 빌드 시 `NEXT_PUBLIC_API_BASE_URL=""`로 박힘 → `lib/api.ts`가 상대 경로 fetch
- 접근: `http://150.230.252.125/` (도메인 없음, IP 직접). HTTPS/도메인은 추후.
- nginx config: `infra/nginx/genie.conf` (서버 1회 수동 반영, 절차는 `docs/infra.md`)
