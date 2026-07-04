# KIS API 연결 예외 처리 개선 — 설계

- 작성일: 2026-07-04
- 상태: 설계 승인 대기 → 구현 계획 예정
- 관련 사건: KIS(한국투자증권) API 서버 점검 다운 시 스케줄 잡 크래시

## 1. 배경 / 문제 정의

KIS API(`openapi.koreainvestment.com:9443`)가 서버 점검으로 다운되면 `requests.get()` 자체에서
`requests.ConnectionError`가 발생한다. 이 연결 레벨 예외를 아무도 처리하지 않아, 이를 호출하는
**예외 처리 없는 스케줄 잡**이 매 실행마다 크래시하고 로그에 전체 트레이스백이 도배된다.

관측된 크래시 경로 (2026-07-04, journalctl):
- `scheduled_tasks/tasks.py:update_data` → `GoogleSheetDataCollector.collect_price()`
  → `hantu_api.get_stock_price("M04020000")` (금 시세) → `requests.get()` 에서 `ConnectionError`.

`_validate_response`(`base_api.py:85`)는 HTTP 응답이 **돌아온 뒤**의 검증(비-200, `rt_cd != "0"`)만
하므로, 연결 자체가 안 되는 경우는 그 앞단에서 이미 예외가 터진다.

### 이미 방어된 경로 (수정 불필요)

예상치/차트 조회 경로는 이미 복원력이 있다:
- `KisEstimateClient.fetch`(`kis_estimate_client.py:146`): tenacity `retry_if_exception_type((requests.RequestException, KisRateLimitError))` 5회 재시도.
- `IncomeStatementService._append_estimates`(`income_statement_service.py:140`): `except Exception` best-effort → 원본 반환(추정치만 미표시).

→ KIS 점검 중에도 차트/손익 조회는 크래시하지 않는다. 이 경로는 건드리지 않는다.

### 실제로 크래시하는 잡 (수정 대상)

방어가 전혀 없는 KIS 의존 스케줄 잡:
1. `update_data` → `collect_price()` (구글시트 금/환율 갱신)
2. `report` → `Reporter.report()` (Slack 금/환율/프리미엄 리포트) — `reporter.py:29`에서 동일하게 `get_stock_price("M04020000")` 호출.

## 2. 목표

- KIS 서버가 응답하지 않아도(연결 거부, 타임아웃, 점검 HTTP 503/HTML 등) 스케줄 잡이 크래시하지
  않고 자연스럽게 이어진다.
- 매매 주문 경로는 **조용히 실패하지 않는다** — 실패는 반드시 예외로 표면화되어야 한다.
- 로그는 트레이스백 없이 한 줄 warning으로 축약한다.
- 기존에 이미 방어된 경로(예상치/차트의 tenacity 재시도)의 동작을 깨지 않는다.

## 3. 설계 (3계층)

### 계층 1 — 전용 예외 타입 (`src/hantu/exceptions.py`, 신규)

```python
import requests

class HantuConnectionError(requests.exceptions.RequestException):
    """KIS API 서버 연결 불가(점검/네트워크 장애 등 전송 계층 실패).

    requests.exceptions.RequestException 하위로 정의하여, 기존 KIS provider들의
    tenacity `retry_if_exception_type(requests.RequestException)` 및
    `except requests.RequestException` 블록과 완전 호환된다.
    """
```

**부모 타입 결정 근거:** 모든 KIS provider 클라이언트(`kis_estimate_client`,
`kis_financial_ratio_client`, `kis_income_statement_client`, `kis_company_client`)가
`requests.RequestException`으로 재시도·catch한다. `requests.ConnectionError`/`Timeout`을
콕 집어 잡는 코드는 hantu 경로에 없다(`common/http_client.py`는 별개 범용 클라이언트).
따라서 `RequestException` 하위로 두면 기존 동작 무손상. (교차검증으로 확인됨)

### 계층 2 — 공통 요청 헬퍼 (`HantuBaseAPI._request`, `base_api.py`)

```python
def _request(self, method: str, url: str, **kwargs: Any) -> Response:
    kwargs.setdefault("timeout", (5, 30))  # (connect 5s, read 30s) — hang 방지
    try:
        return requests.request(method, url, **kwargs)
    except (requests.ConnectionError, requests.Timeout) as e:
        logger.warning("KIS API 연결 실패 [%s %s]: %s", method.upper(), url, e)
        raise HantuConnectionError(str(e)) from e
```

- **번역만, 삼키지 않음:** 연결 실패를 타입 있는 예외로 바꿔 그대로 raise. 매매 주문·토큰
  경로는 여전히 실패로 터진다.
- **기본 timeout 강제(교차검증 CRITICAL):** timeout 인자가 없으면 `requests`는 무한 대기한다.
  점검 중 half-open 커넥션에서 소켓이 영구 블록되면 APScheduler 워커 스레드가 점유되어 매매
  잡까지 마비될 수 있다(크래시보다 나쁨). `read=30s`는 정상 응답엔 걸리지 않을 만큼 넉넉하게.
  - 매매 주문 timeout 시 "체결 여부 모호" 위험은 존재하나, `HantuConnectionError`로 failed
    표면화되므로(침묵 아님) 이중주문보다 안전. read 여유값으로 정상 케이스 오작동을 배제.

### 계층 3 — 호출부 교체 및 소비자 방어

**3a. 요청 호출부 18곳 교체:** `domestic_api.py`(11) + `overseas_api.py`(6) +
`base_api._make_token`(1)의 `requests.get/post(...)` → `self._request("get"/"post", ...)`.
`**kwargs`(headers, params, data)는 투명 전달. `_validate_response` 호출은 변경 없이 유지.

**3b. `collect_price` 부분 업데이트 (`price_data_collector.py`):**
소스 간 데이터 의존성을 반영한 **2블록 구조**로 작성한다.
- 블록 A: `usd_krw`(yfinance) → 성공 시 그 블록 안에서 `international_gold`(FDR × usd_krw) 파생.
  - `international_gold`는 `usd_krw`에 의존하므로 평면 3-try는 `UnboundLocalError`를 유발한다.
- 블록 B: `domestic_gold`(KIS) — 독립.
- 각 블록은 `except Exception`으로 넓게 잡는다(best-effort 소비자). 점검이 HTTP 503/HTML로 와서
  `res.json()`이 `JSONDecodeError`를 던지는 경우까지 커버 (교차검증 Major).
- 실패 시 `logger.warning("...수집 실패, 건너뜀: %s", e)` 한 줄. 성공분만 `updates`에 축적.
- `updates`가 비어있지 않을 때만 `batch_update` 호출.
- row별 `CellUpdate.data`와 `CellUpdate.now`는 **같은 성공 블록에서 쌍으로** 추가해, 실패한
  소스의 타임스탬프가 최신처럼 갱신되지 않게 한다.

**3c. `report` 방어 (`reporter.py` 또는 `tasks.py:report`):**
`report()`는 금/달러 프리미엄을 교차 계산해 **하나의 Slack 메시지**를 만들므로 셀별 부분 업데이트가
성립하지 않는다. 동일 정책의 자연스러운 적용은 **"KIS 등 필수 데이터 조회 실패 시 이번 사이클
리포트를 스킵(한 줄 warning) + 크래시 안 함"**이다.
- 구현 위치는 `Reporter.report()` 내부를 `except Exception` 가드로 감싸 스킵하거나,
  `tasks.py:report` 잡 래퍼에서 처리. (구현 계획에서 확정)

## 4. 로그 정책

- 실패 시 한 줄 `logger.warning`, 트레이스백 없음.
- **쿨다운/억제는 넣지 않는다**(사용자 결정, YAGNI). 다시간 점검 시 `update_data`(1분 주기) 기준
  시간당 ~60줄이 Logtail로 나가지만, 트레이스백이 사라져 부담이 작고 개인 시스템 가시성 관점에서
  허용 가능.

## 5. 안전성 / 회귀 (교차검증으로 확인됨)

- `HantuConnectionError(RequestException)` → 예상치/차트의 tenacity 재시도 그대로 보존.
- 매매 주문 경로 — `infinite_buying`이 per-intent `except Exception`으로 **failed 기록**(침묵 아님).
- `@db_scoped`(`scope.py`)는 예외를 삼키지 않으며, `collect_price`/`report`는 DB 미사용이라
  commit/rollback이 no-op → 부분 업데이트 로직과 충돌 없음.

## 6. 명시적 비목표 (YAGNI)

- 재시도/서킷브레이커 신규 추가 안 함(점검은 장시간 다운 → 매분 재시도는 실익 없음).
- 예외 타입을 `HantuConnectionError`/`HantuTimeoutError`로 분리하지 않음(현 소비자는 모두
  `RequestException`/`Exception`으로 뭉뚱그려 처리하므로 단일 타입으로 충분).
- `_validate_response`/`_make_token`의 bare `Exception` 개선은 이번 범위 밖.

## 7. 테스트 (핵심만)

- **Unit — `_request` 변환:** `requests.request`가 `ConnectionError`/`Timeout`을 던지면
  `HantuConnectionError`로 변환, 그 외 정상 응답은 통과. timeout 기본값 주입 검증.
- **Integration — `collect_price` 부분 업데이트:**
  - domestic(KIS) 실패 → 환율·국제금 셀은 갱신되고 domestic만 스킵, 예외 전파 없음.
  - usd_krw(yfinance) 실패 → international도 스킵되고 `UnboundLocalError` 없음.
  - 전체 성공 소스 없음 → `batch_update` 미호출.
- **회귀 — 재시도 보존:** estimate client가 `HantuConnectionError`(RequestException 하위)를
  tenacity로 재시도함을 확인.
- 구현 시 기존 hantu 테스트의 mock 패치 지점(`requests.get`/`requests.post`)을 `_request`
  또는 `requests.request` 기준으로 조정.

## 8. 검증 체크리스트

`ruff check src/` → `mypy src/` → `pytest tests/` 순으로 통과. 18곳 교체 회귀는 전체 테스트로 확인.
