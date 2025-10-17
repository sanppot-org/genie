# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

`genie`는 Upbit 암호화폐 거래소 API를 위한 Python 래퍼 라이브러리입니다. 타입 안전성을 위해 Pydantic을 사용하며, TDD 방식으로 개발되었습니다.

## 주요 기능

- **시세 조회**: 현재가, 캔들 데이터 조회
- **계좌 관리**: 잔고 조회
- **주문 관리**: 시장가 매수/매도 주문
- **타입 안전성**: Pydantic 모델을 통한 데이터 검증
- **설정 관리**: pydantic-settings를 통한 환경 변수 관리

## 코드 구조

```
src/
├── config.py                    # Config 클래스 (API 키 관리)
├── constants.py                 # 상수 정의
├── upbit/
│   ├── upbit_api.py            # UpbitAPI 클래스, 공개 API 함수
│   └── model/                  # Pydantic 모델
│       ├── candle.py           # CandleData, CandleInterval
│       ├── balance.py          # Balance
│       ├── order.py            # Order
│       └── error.py            # ErrorResponse
tests/
├── test_config.py              # Config 테스트
└── upbit/
    ├── test_upbit_api.py       # API 테스트
    ├── test_upbit_api_config_integration.py  # 통합 테스트
    └── model/                  # 모델 테스트
        ├── test_candle.py
        ├── test_balance.py
        └── test_order.py
```

## 개발 환경

### Python 환경

- Python 3.12+ 필요
- uv 패키지 매니저 사용

### 주요 의존성

- `pydantic>=2.0.0`: 데이터 모델 및 검증
- `pydantic-settings>=2.0.0`: 환경 변수 관리
- `pyupbit>=0.2.34`: Upbit API 클라이언트
- `pandas>=2.0.0`: 데이터 처리
- `requests>=2.31.0`: HTTP 요청
- `pytest>=8.0.0`: 테스트 프레임워크

### 환경 설정

```bash
# 가상 환경 활성화
source .venv/bin/activate

# 의존성 설치
uv pip install -e .

# 테스트 실행 (항상 uv 사용)
uv run pytest tests/

# 특정 테스트 실행
uv run pytest tests/upbit/test_upbit_api.py -v
```

### Git Submodule 관리

`config/` 디렉토리는 git submodule로 관리되며 민감한 설정 파일들을 포함합니다.

```bash
# 최초 클론 시 submodule 초기화
git submodule update --init --recursive

# submodule 업데이트
git submodule update --remote
```

## 개발 가이드라인

### TDD 방식

- 테스트를 먼저 작성한 후 구현
- 행위 검증보다는 **상태 검증**을 적극 활용
- 테스트에 꼭 필요한 필드가 아니라면 임의 생성 값 사용

### 코드 수정 후 체크리스트

1. 빌드 실행: `uv pip install -e .`
2. 테스트 실행: `uv run pytest tests/`
3. 타입 체크 (선택): `mypy src/`

### API 사용 예제

```python
from src.config import UpbitConfig
from src.upbit.upbit_api import UpbitAPI, get_current_price, get_candles

# 공개 API (인증 불필요)
current_price = get_current_price()
candles = get_candles()

# 인증이 필요한 API
config = UpbitConfig()  # .env에서 API 키 로드
api = UpbitAPI(config)

# 잔고 조회
balances = api.get_balances()
eth_balance = api.get_available_amount(ticker='ETH')

# 주문
buy_order = api.buy_market_order(ticker='KRW-ETH', amount=10000)
sell_order = api.sell_market_order(ticker='KRW-ETH', volume=0.001)
```

## 보안 주의사항

### 민감 정보 관리

- **절대 API 키를 코드에 하드코딩하지 말것**
- `.env` 파일 또는 `config/` submodule에만 저장
- `.gitignore`에 `.env` 포함 확인

### config submodule 취급

- `config/` 디렉토리의 파일 내용을 외부에 노출하지 말것
- Upbit access_key, secret_key는 특히 주의
- 테스트 시에도 실제 API 키 사용 최소화 (Mock 사용 권장)

### 환경 변수

`.env` 파일 예시:

```bash
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here
```

## 테스트 구조

- `tests/test_config.py`: Config 클래스 테스트
- `tests/upbit/model/`: Pydantic 모델 단위 테스트
- `tests/upbit/test_upbit_api.py`: UpbitAPI 클래스 테스트
- `tests/upbit/test_upbit_api_config_integration.py`: Config와 API 통합 테스트

## 참고사항

- 이 프로젝트는 `invest-app`, `sudoku` 등 다른 개인 프로젝트에서 사용됩니다
- 설정 파일은 `config/` submodule을 통해 중앙 관리됩니다
- 테스트 실행 시 uv run pytest를 사용해.