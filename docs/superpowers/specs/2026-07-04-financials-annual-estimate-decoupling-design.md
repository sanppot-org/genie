# 재무요약 연간 뷰 — 예상 조회 디커플링 + fail-fast 설계

## 배경 / 증상

KIS 점검 중 재무요약 **연간 뷰만** 표가 안 뜸(분기는 정상). 사용자 직감대로 KIS 연관이 맞으나,
원인은 데이터 결측이 아니라 **best-effort 예상(추정) 조회가 응답을 붙잡는 것**.

### 근본 원인 (코드·prod DB·prod 로그 교차검증)

- `/financials`(연간) → `get_time_series` → `_append_estimates` → `KisEstimateClient.fetch`(KIS 라이브).
- 예상 append는 **연간에서만** 실행(`if period_type == PERIOD_ANNUAL`) → 분기는 즉시, 연간만 hang.
- `KisEstimateClient.fetch`는 `retry_if_exception_type((requests.RequestException, KisRateLimitError))`로
  **5회 재시도**. v1.45.0의 `HantuConnectionError`는 `requests.RequestException` 하위 → 점검(연결불가) 시에도 재시도됨.
- 점검 중 connect timeout=5s 기준: 토큰 유효 시 5s×5 + 백오프 24s ≈ **49s**, 토큰 만료 시 시도당
  토큰5s+estimate5s ×5 + 24s ≈ **74s** > nginx 기본 60s → **504 → 프론트 "조회 실패"**.
- 확정 연간행은 DB(`stock_income_statements`)에서 오며 KIS와 무관하게 정상(ANNUAL 2622종목, 연결결측 0).

## 설계 (A + 프론트 분리)

### A. 예상 조회 fail-fast (`KisEstimateClient`)

재시도 대상에서 `HantuConnectionError`를 제외. "서버 불가"는 한 요청 안에서 복구되지 않으므로 재시도가
무의미하고 유해(응답 지연). rate-limit·기타 일시 네트워크 오류 재시도는 유지.

```
retry = retry_if_exception_type((requests.RequestException, KisRateLimitError))
        & retry_if_not_exception_type(HantuConnectionError)
```

효과: 점검 중 예상 조회는 1회 시도(~5s)로 실패 → 서비스가 best-effort로 조용히 생략. 배치/주문 경로는
`KisEstimateClient`를 쓰지 않아 영향 없음(읽기 경로 전용, sync 없음).

### 프론트 분리 (표를 예상 조회에서 완전히 분리)

- `/financials`(연간/분기): **DB 확정행만** 반환 → 항상 즉시. (`get_time_series`에서 estimate append 제거)
- `/financials/estimates`(신규, 연간 전용): 예상행만 반환. (`get_annual_estimates`)
- 프론트: 두 쿼리를 **병렬**로 요청. 확정 표는 즉시 렌더, 예상행은 도착 시 위에 병합, 실패 시 조용히 생략.

### 서비스 리팩터

- `get_time_series(...)`: 예상 append 블록 제거 → 확정행만.
- `_append_estimates(...)` → `_build_estimates(...)`: `points + result` 대신 **예상행 리스트만** 반환.
- 신규 `get_annual_estimates(ticker_code)`: 확정 연간 시계열을 재계산해 base_eps/base_ni/latest_close를
  도출한 뒤 `_build_estimates`로 예상행만 반환.

## 검증

- 백엔드: ruff → mypy → pytest.
  - `KisEstimateClient.fetch`가 `HantuConnectionError`를 **재시도 없이**(호출 1회) 전파.
  - `get_time_series(ANNUAL)`는 is_estimate 행 없음. `get_annual_estimates`는 is_estimate 행 반환.
- 프론트: `pnpm --dir web lint` + `pnpm --dir web build`.

## YAGNI (비목표)

- 추정치 DB 적재(Option C)는 이번 범위 아님 — 하루 단위로만 바뀌어 라이브 1회로 충분, 별도 과제.
- 예상 조회 timeout 별도 튜닝 불요(fail-fast로 1회 ~5s면 허용 UX).
