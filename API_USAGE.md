# API 사용 가이드

Genie 프로젝트의 VolatilityStrategy 수동 매도 API 사용 방법을 설명합니다.

## 개요

이 API 서버는 다음 기능을 **하나의 프로세스**로 제공합니다:
- ✅ **자동 스케줄링**: 5분마다 전략 실행, 1분마다 데이터 업데이트
- ✅ **수동 매도 API**: 필요할 때 즉시 매도 실행
- ✅ **헬스체크 및 모니터링**: API 상태 확인

## 🚀 실행 방법

### 단일 명령으로 모든 기능 실행

```bash
# API 서버 + 스케줄러 통합 실행
uv run uvicorn src.api:app --reload --port 8000
```

이 명령 하나로:
- API 서버가 `http://localhost:8000`에서 실행됩니다
- 백그라운드 스케줄러가 자동으로 시작됩니다
- 즉시 전략이 한 번 실행됩니다

### 레거시 방식 (선택사항)

스케줄러만 실행하고 싶다면:

```bash
# API 없이 스케줄러만 실행 (레거시 방식)
uv run python main.py
```

⚠️ **권장하지 않음**: 이 방식은 API 기능을 사용할 수 없으므로 통합 서버 사용을 권장합니다.

## API 엔드포인트

### 루트 엔드포인트

```bash
GET /
```

**응답 예시:**
```json
{
  "message": "Genie Trading Strategy API"
}
```

### 헬스체크

```bash
GET /health
```

**응답 예시:**
```json
{
  "status": "ok"
}
```

### 수동 매도 실행

```bash
POST /api/strategy/sell
```

**요청 바디 (선택사항):**
```json
{
  "ticker": "KRW-BTC"
}
```

- `ticker` (optional): 매도할 티커. 생략하면 기본 티커(`KRW-BTC`) 사용

**응답 예시 - 성공 (전량 체결):**
```json
{
  "success": true,
  "message": "매도가 완전히 체결되었습니다.",
  "executed_volume": 0.5,
  "remaining_volume": 0.0
}
```

**응답 예시 - 성공 (부분 체결):**
```json
{
  "success": true,
  "message": "매도가 부분 체결되었습니다.",
  "executed_volume": 0.3,
  "remaining_volume": 0.2
}
```

**응답 예시 - 실패 (캐시 없음):**
```json
{
  "success": false,
  "message": "캐시가 존재하지 않습니다.",
  "executed_volume": null,
  "remaining_volume": null
}
```

**응답 예시 - 실패 (포지션 없음):**
```json
{
  "success": false,
  "message": "오늘 매수한 포지션이 없습니다.",
  "executed_volume": null,
  "remaining_volume": null
}
```

**에러 응답 (유효하지 않은 티커):**
```json
{
  "detail": "유효하지 않은 ticker입니다. 사용 가능한 ticker: ['KRW-BTC', 'KRW-ETH', 'KRW-XRP']"
}
```
HTTP 상태 코드: `400 Bad Request`

## 사용 예시

### cURL

```bash
# 기본 티커로 매도
curl -X POST http://localhost:8000/api/strategy/sell \
  -H "Content-Type: application/json" \
  -d '{}'

# 특정 티커로 매도
curl -X POST http://localhost:8000/api/strategy/sell \
  -H "Content-Type: application/json" \
  -d '{"ticker": "KRW-ETH"}'
```

### Python requests

```python
import requests

# 기본 티커로 매도
response = requests.post('http://localhost:8000/api/strategy/sell', json={})
print(response.json())

# 특정 티커로 매도
response = requests.post(
    'http://localhost:8000/api/strategy/sell',
    json={'ticker': 'KRW-ETH'}
)
print(response.json())
```

### httpie

```bash
# 기본 티커로 매도
http POST http://localhost:8000/api/strategy/sell

# 특정 티커로 매도
http POST http://localhost:8000/api/strategy/sell ticker=KRW-ETH
```

## API 문서 (Swagger UI)

FastAPI는 자동으로 대화형 API 문서를 제공합니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

브라우저에서 위 URL에 접속하면 API를 테스트하고 문서를 확인할 수 있습니다.

## 주의사항

### 스케줄러 자동 실행

API 서버 시작 시 스케줄러가 자동으로 시작됩니다:
- **5분마다**: 자동 매매 전략 실행 (`run_strategies`)
- **1분마다**: 구글 시트 데이터 업데이트 (`update_data`)
- **매일 23:15**: Upbit, Bithumb KRW 잔고 업데이트
- **평일 07-21시 56분**: 리포트 업데이트

### 실행 환경

- `.env` 파일의 Upbit API 키가 필요합니다
- 실제 거래가 발생하므로 **프로덕션 환경에서는 주의**하세요
- `--reload` 옵션은 개발용입니다 (프로덕션에서는 제거 권장)

### 로깅

- API 호출과 스케줄러 실행이 모두 로그에 기록됩니다
- Better Stack 로깅이 자동으로 설정됩니다
- 로그 확인으로 수동/자동 실행을 구분할 수 있습니다

## 테스트

API 테스트는 다음 명령으로 실행할 수 있습니다:

```bash
# API 테스트만 실행
uv run pytest tests/api/ -v

# 전체 테스트 실행
uv run pytest tests/ -v
```

## 프로덕션 실행

프로덕션 환경에서는 `--reload` 옵션을 제거하고 실행하세요:

```bash
# 프로덕션 실행 (리로드 없음)
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000

# 또는 워커 수 지정
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --workers 4
```

### systemd 서비스 예시

```ini
[Unit]
Description=Genie Trading API
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/genie
ExecStart=/path/to/uv run uvicorn src.api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 문제 해결

### 포트 충돌

다른 프로세스가 8000 포트를 사용 중이라면 다른 포트로 실행:

```bash
uv run uvicorn src.api:app --reload --port 8080
```

### 의존성 문제

FastAPI 또는 uvicorn이 설치되지 않은 경우:

```bash
uv pip install -e .
```

### 환경 변수 문제

`.env` 파일에 Upbit API 키가 설정되어 있는지 확인:

```bash
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key
```

### 스케줄러가 시작되지 않는 경우

로그를 확인하여 Upbit 상태 체크나 초기화 문제를 확인하세요:

```bash
# API 서버 로그 확인
# Better Stack 로그 또는 터미널 출력 참조
```
