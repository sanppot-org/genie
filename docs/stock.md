# 주식 데이터 수집

- 주식 데이터를 수집해서 DB에 저장한다.
- 한국 주식을 시작으로 추후에는 다른 시장(미국 등)이나 다른 자산(코인 등)을 추가할 수 있다.
- 일봉을 시작으로 추후에는 분봉도 추가한다. 

- **데이터소스**: pykrx를 이용해서 한국 주식 데이터를 요청. (추후 미국 등 외국 주식 데이터 수집 기능 추가 예정)
- 매일 종목 정보를 수집해서 DB에 저장. 새로 추가되거나 사라지는 경우가 있다.
- 매일 일봉 데이터를 수집해서 DB에 저장한다.

## 테이블 구조
- 종목 정보: tickers
  - id
  - ticker
  - name
  - asset_type: 구분. (주식, ETF, 코인 등)
  - active: 활성화 여부. (True, False)
  - data_source: 데이터 소스. (pykrx, yahoo finance 등)

## 화면
- 종목 목록 조회


## TODO
[x] tickers 테이블 고도화
  [x] name, active 컬럼 추가
  [x] data_source eunm에 PYKRX 추가
[x] pykrx 연동
  [x] pykrx 의존성 추가 (pyproject.toml + mypy override)
  [x] PykrxTickerClient 구현 (주식 + ETF 종목 코드/이름 조회)
  [x] 단위 테스트 (mock)
[ ] 종목 정보 데이터 수집
  [x] PykrxTickerInfo → Ticker 엔티티 변환 로직
  [ ] 신규 종목 INSERT
  [ ] 사라진 종목 active=False (soft-delete)
  [ ] 이름이 변경된 경우 name 업데이트
  [ ] 재상장 시 active=True 복구
  [ ] active 보존을 위한 동기화 전용 서비스 메서드 (TickerCreate 우회)
  [ ] 통합 테스트 (인메모리 DB)
[ ] 종목 정보 수집 스케줄러 구현
  [ ] APScheduler 작업 등록 (장 마감 후 1회, 예: KST 17:00)
  [ ] 휴장일 가드 (주말/공휴일에 호출 skip)
  [ ] 실패 시 Slack 알림