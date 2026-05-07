리펙터링 로그

## 2026-02-21: candle_repositories.py Template Method 패턴 적용

- **AS-IS**: ReadOnly/WritableCandleRepository에 동일한 추상 메서드 6개 중복, 구체 클래스 3개에서 get_candles/get_latest/get_oldest 9개 메서드 copy-paste (423줄)
- **TO-BE**: `CandleQueryMixin`으로 조회 로직 1벌 통합, 서브클래스는 `_get_time_column()`만 오버라이드 (215줄)
- **삭제**: 208줄 (49% 감소), 588개 테스트 전체 통과, mypy/ruff 클린