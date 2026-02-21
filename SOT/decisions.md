의사결정 기록

## 2026-02-21: 테스트 코드 정리 기준 수립

### 배경
테스트 코드에서 중복, 레이어 혼합, 프레임워크 보장 기능 재검증, 극소 파일 등의 문제가 발견되어 정리를 수행함.

### 삭제/축소 판단 기준

1. **Conftest 중복 제거**: 동일한 DB fixture가 `database/conftest.py`와 `service/conftest.py`에 복사되어 있으면 `tests/conftest.py`(루트)로 통합한다.
2. **레이어 혼합 금지**: API 테스트 파일에 리포지토리 레벨 테스트가 섞여 있으면 제거한다. 각 레이어는 자기 테스트 파일에서만 검증한다.
3. **프레임워크 보장 테스트 제거**: Pydantic enum 값 검증, 모델 생성자 호출 후 동일값 assert, 필수 필드 누락 ValidationError 등 프레임워크가 이미 보장하는 기능은 테스트하지 않는다.
   - **유지 대상**: alias 직렬화, API 응답 파싱, 비즈니스 기본값 등 커스텀 로직이 포함된 경우
4. **극소 파일 병합/삭제**: 테스트 1~2개만 있는 파일은 관련 파일에 병합하거나, 다른 테스트에서 암묵적으로 검증되면 삭제한다.

### 결과
- 삭제된 파일 4개: `database/conftest.py`, `test_hantu_stock_price.py`, `test_ticker.py`, `test_database.py`, `test_constants.py`
- 축소된 파일 4개: `test_ticker_api.py`, `test_chart.py`, `test_hantu_order.py`, `test_price.py`
- 생성된 파일 1개: `tests/conftest.py`
- 총 약 490줄 삭제, 588개 테스트 전체 통과 확인