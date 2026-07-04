# 백테스트 결과 차트 (Equity Curve + Drawdown) 설계

- 날짜: 2026-07-04
- 상태: 승인됨 (사용자)

## 목적

Lab 백테스트 결과에서 수익률과 MDD를 시계열로 자세히 볼 수 있도록,
전략별 equity curve(수익률 %)와 drawdown(낙폭 %) 2단 차트를 추가한다.
Buy & Hold 벤치마크 라인을 함께 그려 전략 성과를 상대 비교할 수 있게 한다.

## 접근 방식

**TimeReturn 분석기 + 기존 응답 확장.** backtrader 표준 `TimeReturn(timeframe=Days)`
분석기로 일별 수익률 시계열을 얻어 `/backtest/run` 응답에 포함한다.
백테스트 1회 실행으로 표와 차트를 모두 채운다 (별도 엔드포인트/재실행 없음).
1h/1m 전략도 일 단위로 집계되어 포인트 수가 자연스럽게 제한된다.

배제한 대안: ① 별도 시계열 엔드포인트(백테스트 중복 실행, 표-차트 불일치 위험),
② 프론트에서 trade_history 재구성(미실현 손익 미반영으로 drawdown 부정확).

## 변경 사항

### 백엔드

1. `src/backtest/backtest_builder.py` — `_STANDARD_ANALYZERS`에
   `TimeReturn(timeframe=Days)` 추가, `run_with_result()`에서 시계열 추출.
2. `src/backtest/result.py` — `EquityPoint(date, return_pct, drawdown_pct)` 및
   `BacktestResult.equity_curve: list[EquityPoint] | None` 추가.
   equity curve는 일별 수익률 누적곱, drawdown은 running peak 대비 %.
   `to_dict()`에서는 시계열 제외 (CSV 내보내기 오염 방지).
3. `src/service/backtest_service.py` — 이미 로드한 캔들 종가로 Buy & Hold
   벤치마크 시계열 1개 계산 → `BacktestRunOutput.benchmark`.
4. `src/api/schemas.py` + `src/api/routes/lab.py` —
   `BacktestRunItem.equity_curve`, `BacktestRunResponse.benchmark` 추가.
   다운샘플링 없음 (일봉 30년 ≈ 전략당 9,000포인트, YAGNI).

### 프론트엔드

5. `web/components/backtest-chart.tsx` 신규 — `compare-chart.tsx` 패턴
   (lightweight-charts + `compare-colors.ts` PALETTE). 단일 차트 2-pane:
   위 = 전략별 equity curve + 벤치마크(회색 점선), 아래 = 전략별 drawdown.
   각 전략 MDD 최저점 마커 표시. bust 전략 제외.
6. `web/app/lab/page.tsx` — 결과 테이블 위에 차트 삽입, `web/lib/types.ts` 타입 추가.

## 테스트

- 백엔드: equity curve 산출 검증 (마지막 포인트 = total_return_pct, 최저 drawdown ≈ MDD),
  벤치마크 계산 검증. `uv run ruff check` → `mypy` → `pytest`.
- 프론트: `pnpm --dir web lint` + `pnpm --dir web build`.
