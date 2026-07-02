---
name: adding-backtest-strategy
description: Use when adding a new trading strategy to the genie backtest system, registering a backtrader Strategy, or when STRATEGY_REGISTRY / scripts/backtest.py / test_registry.py need a new entry. Symptoms - "새 전략 백테스트", "전략 추가", registry test failing after adding a strategy.
---

# 새 백테스트 전략 추가

## Overview

genie의 백테스트 전략은 backtrader `bt.Strategy` 클래스 + `STRATEGY_REGISTRY` 등록으로 구성된다.
등록만 하면 CLI(`scripts/backtest.py`)와 웹 Lab 페이지에 자동 노출된다 — API/프론트 수정 불필요.

## Workflow

1. **전략 클래스** — `src/backtest/strategy/<name>_strategy.py` 생성 (컨벤션은 아래)
2. **레지스트리 등록** — `src/backtest/registry.py`: import 추가 + `STRATEGY_REGISTRY`에 `StrategySpec` 엔트리 추가. 상단 `# 레지스트리 — N개 전략 등록` 주석의 개수도 갱신
3. **⚠️ test_registry.py 갱신 (필수)** — `tests/backtest/test_registry.py`가 전략 개수·목록을 하드코딩함. 안 고치면 pytest 3개 실패:
   - `EXPECTED_STRATEGIES` dict에 `"이름": (클래스, "타임프레임", cheat_on_open여부)` 추가 + import
   - `assert len(STRATEGY_REGISTRY) == N` 및 `assert len(names) == N`의 N 증가 (2곳)
   - 테스트 메서드명(`test_registry_has_all_eight_strategies`)과 docstring에도 개수가 박혀 있음 — 함께 갱신
4. **전략 테스트 (권장)** — `tests/backtest/strategy/test_<name>_strategy.py`: 합성 캔들 DataFrame → `bt.Cerebro` 직접 구동, `strategy.buy_executed` 플래그 검증. 패턴은 `test_volatility_breakout_strategy.py` 참고. 핵심 성공 케이스 1개면 충분 (프로젝트 TDD 가이드라인). ⚠️ 표준편차 기반 지표(볼린저 등)는 완전히 평평한 합성 데이터에서 stddev=0으로 밴드가 붕괴해 오탐 — 워밍업 구간에 변동을 넣을 것
5. **검증 & 실행** — ruff → mypy → pytest 순서 후 CLI 실행

## StrategySpec 결정 가이드

| 필드 | 규칙 |
|---|---|
| `timeframe` | `"1d"`/`"1h"`/`"1m"` — 해당 타임프레임 캔들이 DB에 백필돼 있어야 함 |
| `default_sizer` | 대부분 `SizerConfig.percent(95)`. 전략이 `self.buy(size=...)`로 직접 수량 계산하면 `None` + `manages_own_sizing=True` |
| `requires_cheat_on_open` | `next_open()`으로 시가 체결하는 전략만 `True` (예: timed_hold) |
| `initial_cash`/`commission` | **등록하지 않음** — 공정 비교를 위해 CLI 전역 설정 |

## 전략 클래스 컨벤션

- 한국어 docstring (진입/청산 조건, Params, Example 포함)
- `params = (("key", default),)` 튜플 + `self.params.key` 접근에 `# type: ignore[attr-defined]`
- `log()`, `notify_order()`, `trade_history` 리스트(시각화용) 보일러플레이트 — `volatility_breakout_strategy.py`에서 복사가 기준
- 테스트용 플래그: `self.buy_executed = False`, `self.sell_executed = False` → `notify_order`의 Completed 분기에서 True
- RSI는 `bt.indicators.RSI_Safe` 사용 (ZeroDivision 방지). 지표 워밍업(`minperiod`)은 backtrader가 자동 처리 — start 직후 N봉은 신호 없음
- 청산은 `self.sell()` (프로젝트 컨벤션, PercentSizer가 보유 시 전량 반환)

## 실행 명령

```bash
uv run python scripts/backtest.py --list-strategies   # 등록 확인

# 벤치마크(buy_and_hold)와 비교 — ENV_PROFILE=local 필수 (.env.dev가 prod DB를 가리킬 수 있음)
ENV_PROFILE=local uv run python scripts/backtest.py \
  --ticker TQQQ --strategy buy_and_hold,my_strategy --start 20200101 --end 20241231

# 파라미터 튜닝 — ⚠️ --param은 단일 전략일 때만 허용 (scripts/backtest.py:159)
ENV_PROFILE=local uv run python scripts/backtest.py \
  --ticker TQQQ --strategy my_strategy --start 20200101 --end 20241231 --param key=value

# --csv /path.csv 로 결과 저장 가능
```

## 선행 조건 & 함정

- **캔들 백필**: 티커 미등록이면 CLI가 명확한 에러로 종료. US 주식: `scripts/register_us_tickers.py` → `scripts/backfill_us_daily_candles.py`. 크립토는 `--asset crypto`
- **수정주가**: `adj_close`가 NULL이면 raw 주가 사용 + WARNING — 분할 이력 종목(TQQQ 등)은 결과 왜곡됨
- **DB 프로필**: 백테스트는 읽기 전용이지만 `ENV_PROFILE=local` 명시 권장

## Common Mistakes

| 실수 | 결과 |
|---|---|
| test_registry.py 미갱신 | pytest 3개 실패 (개수 하드코딩) |
| 다중 전략 + `--param` | CLI가 에러 종료 |
| `manages_own_sizing=True`인데 sizer 지정 | 이중 사이징 버그 |
| 커스텀 sizer가 전략 속성에 의존 (예: EmaDynamicSizer) | 다른 전략과 조합 시 AttributeError |
