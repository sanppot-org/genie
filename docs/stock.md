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


## TODO
[ ] tickers 테이블 고도화
  [ ] name, active 컬럼 추가
  [ ] data_source eunm에 PYKRX 추가
[ ] pykrx 연동
[ ] 종목 정보 데이터 수집
  - 종목 사라진 경우 active=False 처리
  - 이름이 변경된 경우 name 컬럼 업데이트
[ ] 종목 정보 수집 스케줄러 구현