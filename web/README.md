# genie web

Genie 백엔드(FastAPI) 데이터 분석·차트 뷰어 (Next.js + TypeScript + TailwindCSS + shadcn/ui + TanStack Query).

## 실행

```bash
pnpm install
cp .env.example .env.local   # 최초 1회. NEXT_PUBLIC_API_BASE_URL 확인.
pnpm dev                     # http://localhost:3000
```

백엔드(`uvicorn app:app --host 0.0.0.0 --port 8000`)가 떠 있어야 한다. CORS는 백엔드 `CORS_ALLOW_ORIGINS` 환경변수에서 허용 origin 관리 (기본 `http://localhost:3000`).

## 구조

- `app/` — Next.js App Router 라우트
  - `providers.tsx` — TanStack Query Provider (`staleTime=60s`, `retry=1`)
  - `layout.tsx` — RootLayout + Providers wrap
- `components/ui/` — shadcn/ui 컴포넌트 (필요할 때 `pnpm dlx shadcn@latest add <name>`)
- `lib/api.ts` — fetch 래퍼 (`apiGet`/`apiPost`, `NEXT_PUBLIC_API_BASE_URL` 기반)
- `lib/utils.ts` — `cn` helper (shadcn 기본)

## 컴포넌트 추가

```bash
pnpm dlx shadcn@latest add button card input table
```

## 스크립트

- `pnpm dev` — 개발 서버
- `pnpm build` — 프로덕션 빌드
- `pnpm start` — 빌드된 서버 실행
- `pnpm lint` — ESLint
