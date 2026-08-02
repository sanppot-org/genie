# 버그/이슈 해결 기록

최신순 상단. 원인·해결·주의사항 3줄 요약.

## 2026-08-02: 장기 거래정지 후 재개 종목의 분할·감자 감지 누락 → 수정주가가 5배 틀린 값으로 잔존

- **원인**: `find_split_candidate_ticker_ids`가 직전 종가를 **윈도우 내 `LAG`** 로 구하고 스캔 범위를 `scan_from = since - 10일`(= `readjust_recent_splits`의 `lookback_days=10`과 합쳐 총 20일)로 잘랐다. 거래정지가 20일보다 길면 정지 이전 행이 스캔 밖으로 나가 재개 첫 행이 파티션 첫 행이 되고 `prev_close = NULL` → 급변이 후보에서 조용히 탈락. 버퍼 10일은 공휴일 연휴만 가정한 값이나 거래정지는 수 주~수 개월. prod 실측: 미래산업(025560) 21일 정지 후 1:5 감자로 재개했는데 미감지 → DB `adj_close` 60,300 vs 네이버 현재 12,060(**배율 0.200, 정확히 5배 오차**). 동일 패턴 KR모터스·티웨이홀딩스·디젠스·지슨 확인(공백 21~26일), 2026-04-01 이후만 **178종목/181건** 누락. NULL이 아니라 *틀린 값*이라 `price=adjusted` 차트·백테스트에 없던 절벽이 생긴다.
- **해결**: `LAG` → **거리 무관 상관 서브쿼리**(`prv.ticker_id = cur.ticker_id AND prv.date < cur.date ORDER BY prv.date DESC LIMIT 1`)로 교체하고 `scan_from` 버퍼 제거. `ix_stock_daily_candles_ticker_id_date` 역방향 인덱스 스캔으로 행당 1회 조회 → 스캔은 `since` 이후 행 수에만 비례. `prev_close > 0` 이 NULL(첫 거래일)도 걸러내므로 중복 `IS NOT NULL` 제거(참조 1회 = 서브쿼리 재평가 1회라 서브플랜 4→3). prod EXPLAIN ANALYZE: 566ms, 후보 4→**19종목**(2026-07-21 이후 윈도우).
- **주의**: ① 감지 밴드(`0.6`/`1.7`)는 그대로 — 이번 수정은 비교 *대상*을 못 찾던 문제이지 임계값 문제가 아니다. ② **이미 오염된 종목의 데이터는 코드 수정으로 복구되지 않는다** — `sync(ticker_codes=...)` 1회 재보정 필요(prod 쓰기 승인 대상, 미실행). ③ 분기 안전망(`resync_all_adjusted_candles`, 1/4/7/10월 1일)이 결국 덮지만 최대 3개월 오염이 남는다. ④ `partial_tickers` 경고는 Slack 미전송이라 부분 보정 실패가 조용히 묻힌다(미수정).
- **참고 — 최근 구간 `adj_close` NULL은 정상**: `adj_*`는 분기 안전망과 분할 감지만 채우고 일일 KR 캔들 동기화는 건드리지 않는다. 분할 없는 종목은 factor가 1.0이라(삼성전자 2019·2022·2025 확인) NULL → 원주가 폴백으로 값이 맞다.

## 2026-06-11: 자회사 주식소각결정 공시가 모회사로 오귀속 (스크리너 소각비율 부풀림) — codex·OMC 교차검증

- **원인**: `DartCompanyClient.fetch_cancellation_events`의 자회사 배제 필터(`row_stock_code != stock_code`)가 무력. DART `list.json`은 `corp_code`로 서버 필터되어 모든 row의 stock_code가 조회 대상(=공시 제출자) 코드 → 비교가 절대 성립 안 함. 모회사가 자회사(주로 비상장) 소각을 대신 공시한 "주식소각결정(자회사의 주요경영사항)"은 제출자=모회사라 stock_code도 모회사 → 키워드·stock_code 필터 둘 다 통과해 자회사 소각이 모회사 `annual_cancel_ratio`(8점)·`regular_buyback`(7점)을 부풀림. prod 실측 892건 중 **36건(21종목)** 오귀속, 35건은 소각수량까지 보유.
- **해결**: 무력한 stock_code 비교를 제거하고 `report_nm`에 `_SUBSIDIARY_DISCLOSURE_MARKER="자회사의 주요경영사항"`(괄호 없는 부분문자열) 포함 시 배제로 교체. document() 원문 fetch 전에 배제. 회귀 테스트 추가(stock_code 동일한 자회사 row 배제 + document 미호출 검증, `__new__`로 OpenDartReader 생성자 우회).
- **데이터 정리 완료(2026-06-11)**: 코드 수정은 미래 적재만 차단하므로 기존 적재분을 일회성 삭제. 트랜잭션+가드(>50건 시 롤백)로 `DELETE … WHERE report_nm LIKE '%(자회사의 주요경영사항)%'` 실행 — **prod(140.245.67.107) 36건 삭제(892→856), 잔존 0 독립 확인**. local docker는 전체 3건·자회사 0건이라 대상 없음. 점수는 실시간 계산이라 다음 조회부터 21종목 자동 정정.
- **주의**: ① 배제 패턴은 정상 자기 공시("주식소각결정"/"[기재정정]주식소각결정")엔 없는 "주요경영사항" 공시 계열 전용이라 false-positive 없음. ② 다른 자회사 공시명 변형이 생기면 마커 누락 가능 — prod `report_nm` 분포 재확인으로 가드.

## 2026-06-10: 배당절차 개선으로 fiscal_year +1 오귀속 → 연속인상 streak=0 (KG케미칼) — codex 2R 교차검증

- **원인**: 배당절차 개선(2023~)으로 12월 결산 종목이 배당기준일을 결산일(12/31)→익년 봄(3~4월)으로 이전. KIS `ksdinfo_dividend`는 봄 실배당 record + `(N-1)-12-31 dps=0 결산` 폐지 placeholder를 함께 내려주는데, ① placeholder는 `dps<=0`이라 적재 제외되어 fiscal 2025 공백, ② 봄 record는 `fiscal_year=record_date.year`(=2026)로 오적재 → `_calc_streak` recency 앵커(`years_desc[0]!=cutoff_year`) 실패로 streak=0. KG케미칼 FY2023 120→FY2024 130→FY2025 150(record 20260415) 연속인상인데 0. prod 동일 패턴(fys⊇{2024,2026}∧2025∉) **117종목**(상승69/동결35/하락12).
- **해결**: sync에서 ticker별 `(N-1)-12-31 dps=0 결산` placeholder 연도를 앵커로 수집 → 봄(1~6월) 결산배당이고 짝 placeholder가 있으면 `fiscal_year=record_year-1` 보정(없으면 미보정 → 상시 봄결산형 오탐 차단). placeholder는 여전히 미적재(앵커 전용). 일일 sync 윈도우 `from_date=min(today-30d,(today.year-1)-12-01)`로 확장해 봄 record와 placeholder 동시 수집. UPSERT 키 `(ticker_id,record_date,kind)`·`set_`에 fiscal_year 포함 → 광역 재동기화로 in-place 보정. 죽은 `divi_aplc_yymm`/`_parse_fiscal_year`·모델 필드 제거(KIS live 미제공 확정: 25,791건 전부 fiscal_year==record_date.year).
- **주의**: ① KIS·DART 모두 특별배당 구분 필드 없음(특별배당은 결산 현금배당에 흡수). ② placeholder만 있고 봄 실배당 없으면 그 해 **무배당**(포스코퓨처엠 FY2024) — (A)는 봄 dps>0일 때만 보정해 무관. ③ **prod 광역 재동기화는 사용자 직접**(로컬 prod 백필 금지), older 봄 record까지 보정하려면 `from`을 2023-12 이상으로. ④ 교차검증은 read-only `codex exec`(또는 `/codex:review`)로, codex-rescue write 경로 금지.
- **prod 재동기화 결과(2026-06-10, from=2023-12-01)**: received 35,460 / upserted 4,428. KG케미칼 `2026-04-15` → fiscal_year 2025 보정 확인(120→130→150 연속 복원). 117종목 중 **114 보정, 3 잔존**.
- **알려진 한계 — placeholder 미발급 종목 미보정(잔존 3)**: KIS가 `(N-1)-12-31 dps=0` placeholder를 **모든 제도변경 종목/연도에 주지 않음**(라이브 확인). 농심(004370): placeholder 전무(구 Dec 실배당→봄 직행), FY2025 6000 미보정. 삼천리(004690): 2023·2024 placeholder는 있으나 2025 누락 → 2026 봄건 미보정. SV인베스트먼트(289080): 상시 3월 결산(Dec 이력 전무) → **미보정이 정당**(제도변경 아님). 강화안("과거 Dec 결산 이력 보유" 판별)은 **결산월 변경(12월→3월) 종목 오보정** + 이력조건 **시점 의존성**(재동기화 시점 따라 fiscal_year 달라짐) 리스크로 codex 교차검증서 단순 전환 기각, 사용자 결정으로 **현재(placeholder 규칙) 수용**. DART 결산월 교차가 유일한 확실 차단책이나 효용 대비 보류. 구조적 재발(제도변경 확산+placeholder 비일관) 가능 — 추후 DART 결산월 도입 시 재검토.

## 2026-05-30: 스크리너 배당연속증가(`_calc_streak`) 정확성 결함 — codex·OMC critic 교차검증

- **누락 연도(gap)가 연속을 끊지 않음(HIGH)**: `dividend_service._calc_streak`이 정렬된 연도 **배열 인덱스**를 인접 비교해, 배당 중단 연도(dps<=0은 sync 미적재 → row 결측)가 있어도 그 양옆 연도를 "연속"으로 잘못 인정. 예: 2020·2021·2023만 있고 2022 중단 → streak=2(정답 0). → 비교 전 `years_desc[i] - years_desc[i+1] != 1`이면 break.
- **recency 앵커 부재(HIGH)**: cutoff는 미래/진행중 연도만 제거할 뿐, 최신 데이터 연도가 cutoff_year인지 미검사 → 수년 전 배당 끊긴 종목도 과거 행진으로 점수 획득. → `years_desc[0] != cutoff_year`면 0 반환. 분기배당(`is_quarterly_dividend_bulk`)·cutoff 5월 경계는 정상 확인.
- **주의(미수정·운영성)**: ① 과거 회계연도가 부분 백필되면 연간 dps 합 과소 → 허위 증감(전체 히스토리 백필 필요). ② `fiscal_year`는 KIS `divi_aplc_yymm`("배당기준연월", record 기준) — 12월 결산은 정상이나 비-12월 결산은 ±1 오귀속 가능. ③ KIS가 분기지급을 "중간"으로 주면 분기배당 미탐지. 회귀 테스트 추가(gap/stale), 충돌하던 기존 테스트는 명시적 `today`로 결정화.

## 2026-05-30: DART 자사주 소각 수집 — 파싱·결측·마이그레이션 이슈

- **소각 구조화 API 부재**: KIS에 자사주 소각 데이터 전무, DART에도 소각 전용 구조화 JSON 없음(OpenDartReader `event()` 미지원). → `list()`로 "주식소각결정" 공시 식별 후 `document()` 원문 정규식 파싱. 주의: 레이블(`소각할 주식의 종류와 수`/`소각예정금액`/`소각 예정일`/`이사회결의일`)은 일정하나 보장은 없음 → 파싱 실패는 raise 말고 WARN+skip, fixture(삼성 20250218800029) 회귀 테스트로 고정.
- **라벨 변형으로 파싱 실패(prod 백필 중 발견)**: 삼성 양식만으로 만든 정규식이 다수 종목 양식을 놓침. ① `이사회결의일(결정일)`(삼성) vs `이사회결의일`(다수, 괄호 없음) → resolution_date 정규식이 `(결정일)`을 필수로 봐 전체 파싱 실패. → `이사회결의일\s*(?:\(결정일\))?\s*(날짜)`로 선택적 처리. ② `발행주식 총수`(공백) vs `발행주식총수`(붙임)은 이미 `\s*`로 무관. 주의: 변형 양식(나무가 190510 등) 회귀 테스트 추가. 실패 문서 4건 재파싱 정상 확인 후 prod 백필 재개.
- **결측 vs 진짜 0(스크리너 점수)**: ③ 자사주 보유 "없음→5점"의 "없음"은 0주(데이터 존재)임. `stock_treasury_stocks` row 자체가 없는 미백필 종목을 5점 주면 최고점 오류 → row 없음=0점+N/A로 처리(결측≠0주). PER/PBR 결측=0 정책과 일치.
- **alembic 015 `id` 컬럼 버그**: `Identity(always=True)` + `nullable=True` 동시 선언 → Postgres `conflicting NULL/NOT NULL`. → `nullable=False`로 수정(014와 동일). 주의: Identity는 NOT NULL 함의.
- **DART 초기 backfill 레이트리밋**: (선행) KIS와 달리 DART 분당 1,000건 여유 있으나, 소각은 종목당 list+공시별 document라 호출량 큼 → 증분 가드 + 백필/스케줄러 분리.
