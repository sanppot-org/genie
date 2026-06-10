# KIS MCP

한국투자증권 OpenAPI MCP 2종. 원본: `open-trading-api/MCP/`.

## 1. KIS Code Assistant MCP

자연어로 API 검색 + 샘플코드 제공 (읽기 전용, 실거래 X). **주식/투자 코드 작성 시 먼저 호출.**

MCP 도구:
- `search_domestic_stock_api` — 국내주식
- `search_overseas_stock_api` — 해외주식
- `search_domestic_futureoption_api` / `search_overseas_futureoption_api` — 선물·옵션
- `search_domestic_bond_api` — 채권
- `search_etfetn_api` — ETF/ETN
- `search_elw_api` — ELW
- `search_auth_api` — 인증/토큰
- `read_source_code` — 검색 결과의 실제 구현 코드 조회

흐름: `search_*_api`로 API 찾기 → `read_source_code`로 예제 코드 확인.

## 2. KIS Trading MCP

OpenAPI를 도구로 래핑해 AI에서 직접 호출 (시세/계좌/주문). 모의/실전 환경 구분.
- 시세: 국내/해외 주식·선물옵션·채권·ETF/ELW
- 계좌: 잔고, 주문/체결내역, 손익
- 주문: 현물/신용/선물옵션 + 정정취소
- 위치: `open-trading-api/MCP/Kis Trading MCP/`. 인증: `kis_devlp.yaml` (App Key/Secret, 계좌번호).

## 인증

- App Key/Secret은 `~/KIS/config/kis_devlp.yaml` 또는 `config/` submodule에만. 공개 저장소 업로드 금지.
- OAuth 토큰 기반. 모의(`vps`) / 실전 분리.
