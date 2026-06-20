# 무한매수법 Phase 2b — KIS 어댑터 확장(LOC/MOC 주문 + 체결조회) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `HantuOverseasAPI`에 무한매수법 v1에 필요한 (1) LOC/MOC 주문 메서드와 (2) 해외주식 체결조회(`inquire-ccnl`)를 추가한다. 기존 패턴(`_order`, `_get_balance_recursive`)을 그대로 따른다.

**Architecture:** 주문은 기존 `_order(order_direction, order_division, ...)`가 `ORD_DVSN`만 바꿔 LOC(34)/MOC(33)을 이미 지원하므로 얇은 public 래퍼만 추가. 체결조회는 잔고조회(`_get_balance_recursive`)와 동형의 GET+연속조회 메서드 + 신규 Pydantic 모델. 실주문/조회 IO는 여기까지, 오케스트레이션(발주잡/대조잡)은 Phase 2c.

**Tech Stack:** Python 3.12, requests, Pydantic v2, pytest + pytest-mock, ruff, mypy, uv.

**참조:** 스펙 §10(v1 범위), Phase 2 조사 결과(체결조회 명세). 명세 근거: `open-trading-api/legacy/Sample01/kis_ovrseastk.py`(get_overseas_inquire_ccnl), `open-trading-api/examples_llm/overseas_stock/inquire_ccnl/`, 기존 `src/hantu/overseas_api.py`.

## Global Constraints

- KIS 명세는 **추측 금지**. 본 계획의 필드명/TR_ID는 코드 근거(위 참조)에서 확정한 값이다:
  - 체결조회 URL `/uapi/overseas-stock/v1/trading/inquire-ccnl`, TR_ID 실전 `TTTS3035R` / 모의 `VTTS3035R`.
  - 주문 URL `/uapi/overseas-stock/v1/trading/order`. 미국 매수 실전 `TTTT1002U`/모의 `VTTT1002U`, 매도 실전 `TTTT1006U`/모의 `VTTT1006U`(기존 `ORDER_TR_ID_MAP`).
  - 주문구분 `ORD_DVSN`: LOC `"34"`, MOC `"33"`, LIMIT `"00"`(기존 `OverseasOrderDivision` enum).
  - 매도 시 `SLL_TYPE="00"`, 매수 시 `""`(기존 `_order` 규칙).
- 체결조회 응답은 단일 `output` 리스트. 핵심 필드(코드 근거): `odno`(주문번호), `pdno`(종목), `sll_buy_dvsn_cd`(01 매도/02 매수), `ft_ord_qty`(주문수량), `ft_ccld_qty`(체결수량), `ft_ccld_unpr3`(체결단가), `nccs_qty`(미체결수량), `ord_dt`(주문일자), `ord_tmd`(주문시각), `prcs_stat_name`(처리상태), `ovrs_excg_cd`(거래소).
- 연속조회: 응답 헤더 `tr_cont` in `["M","F"]`이면 응답 body의 `ctx_area_fk200`/`ctx_area_nk200`로 `tr_cont="N"` 재조회(기존 `_get_balance_recursive`와 동일).
- 모의투자 제약: 주문은 지정가(00)만 가능 → LOC/MOC는 실전에서만 실제 체결(테스트는 모두 mock). 체결조회 모의는 `SLL_BUY_DVSN`/`CCLD_NCCS_DVSN`=00, `SORT_SQN` 미사용.
- 테스트는 `requests.post`/`requests.get`와 `_get_token`을 mock(기존 `tests/hantu/test_overseas_api.py` 패턴). 실제 네트워크 호출 금지.
- Python 3.12, ruff line-length 180, 룰 E,F,W,I,N,UP,ANN,B,A,C4(테스트는 ANN001/201/202·N802 무시). mypy 통과.

---

## File Structure

- `src/hantu/overseas_api.py` (수정) — `buy_loc_order`/`sell_loc_order`/`sell_moc_order` 추가(Task 1); `inquire_ccnl` + `_inquire_ccnl_recursive` 추가(Task 2).
- `src/hantu/model/overseas/execution.py` (생성) — 체결조회 요청/응답 모델(Task 2).
- 테스트: `tests/hantu/test_overseas_api_order_loc_moc.py`(Task 1), `tests/hantu/test_overseas_api_inquire_ccnl.py`(Task 2).

---

## Task 1: LOC/MOC 주문 메서드

**Files:**
- Modify: `src/hantu/overseas_api.py` (public 메서드 추가; `_order`/`ORDER_TR_ID_MAP` 재사용)
- Test: `tests/hantu/test_overseas_api_order_loc_moc.py`

**Interfaces:**
- Consumes: 기존 `_order(order_direction, order_division, exchange_code, ticker, quantity, price)`, `OrderDirection`, `OverseasOrderDivision`(LOC/MOC), `OverseasExchangeCode`, `overseas_order.ResponseBody`.
- Produces:
  - `buy_loc_order(ticker: str, quantity: int, price: str, exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD) -> overseas_order.ResponseBody`
  - `sell_loc_order(ticker: str, quantity: int, price: str, exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD) -> overseas_order.ResponseBody`
  - `sell_moc_order(ticker: str, quantity: int, exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD) -> overseas_order.ResponseBody`

- [ ] **Step 1: Write the failing test**

Create `tests/hantu/test_overseas_api_order_loc_moc.py`:

```python
"""HantuOverseasAPI LOC/MOC 주문 메서드 테스트 (requests mock)."""

import json

from src.config import HantuConfig
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.model.overseas.exchange_code import OverseasExchangeCode
from src.hantu.overseas_api import HantuOverseasAPI


def _order_response(mocker):
    res = mocker.Mock()
    res.status_code = 200
    res.json.return_value = {
        "rt_cd": "0", "msg_cd": "MCA00000", "msg1": "정상처리 되었습니다.",
        "output": {"KRX_FWDG_ORD_ORGNO": "01790", "ODNO": "0030000123", "ORD_TMD": "092000"},
    }
    return res


def _sent_body(post_mock) -> dict:
    """_order는 requests.post(..., data=body.model_dump_json())로 전송 → JSON 파싱."""
    return json.loads(post_mock.call_args.kwargs["data"])


def _sent_tr_id(post_mock) -> str:
    return post_mock.call_args.kwargs["headers"]["tr_id"]


def test_buy_loc_order_sends_loc_division_and_us_buy_tr_id(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    post = mocker.patch("requests.post", return_value=_order_response(mocker))

    out = api.buy_loc_order("TQQQ", 4, "50.00", OverseasExchangeCode.NASD)

    assert out.output.ODNO == "0030000123"
    body = _sent_body(post)
    assert body["ORD_DVSN"] == "34"          # LOC
    assert body["SLL_TYPE"] == ""            # 매수
    assert body["PDNO"] == "TQQQ"
    assert body["ORD_QTY"] == "4"
    assert body["OVRS_ORD_UNPR"] == "50.00"
    assert _sent_tr_id(post) == "TTTT1002U"  # 미국 실전 매수


def test_sell_loc_order_sends_loc_division_and_us_sell_tr_id(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    post = mocker.patch("requests.post", return_value=_order_response(mocker))

    api.sell_loc_order("SOXL", 3, "20.50", OverseasExchangeCode.NASD)

    body = _sent_body(post)
    assert body["ORD_DVSN"] == "34"          # LOC
    assert body["SLL_TYPE"] == "00"          # 매도
    assert body["OVRS_ORD_UNPR"] == "20.50"
    assert _sent_tr_id(post) == "TTTT1006U"  # 미국 실전 매도


def test_sell_moc_order_sends_moc_division_zero_price(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    post = mocker.patch("requests.post", return_value=_order_response(mocker))

    api.sell_moc_order("TQQQ", 10, OverseasExchangeCode.NASD)

    body = _sent_body(post)
    assert body["ORD_DVSN"] == "33"          # MOC (장마감시장가)
    assert body["SLL_TYPE"] == "00"          # 매도
    assert body["OVRS_ORD_UNPR"] == "0"      # 시장가 → 0
    assert _sent_tr_id(post) == "TTTT1006U"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hantu/test_overseas_api_order_loc_moc.py -v`
Expected: FAIL with `AttributeError: 'HantuOverseasAPI' object has no attribute 'buy_loc_order'`

- [ ] **Step 3: Write the implementation**

In `src/hantu/overseas_api.py`, add these three methods right after `sell_limit_order` (the public order methods block, before `_order` at line 509):

```python
    def buy_loc_order(
            self,
            ticker: str,
            quantity: int,
            price: str,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD,
    ) -> overseas_order.ResponseBody:
        """LOC(장마감지정가) 매수 주문. 종가가 지정가 이하로 마감되면 종가로 체결."""
        return self._order(
            order_direction=OrderDirection.BUY,
            order_division=overseas_order.OverseasOrderDivision.LOC,
            exchange_code=exchange_code,
            ticker=ticker,
            quantity=quantity,
            price=price,
        )

    def sell_loc_order(
            self,
            ticker: str,
            quantity: int,
            price: str,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD,
    ) -> overseas_order.ResponseBody:
        """LOC(장마감지정가) 매도 주문. 종가가 지정가 이상으로 마감되면 종가로 체결."""
        return self._order(
            order_direction=OrderDirection.SELL,
            order_division=overseas_order.OverseasOrderDivision.LOC,
            exchange_code=exchange_code,
            ticker=ticker,
            quantity=quantity,
            price=price,
        )

    def sell_moc_order(
            self,
            ticker: str,
            quantity: int,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD,
    ) -> overseas_order.ResponseBody:
        """MOC(장마감시장가) 매도 주문. 종가로 시장가 체결되므로 단가는 0으로 전송."""
        return self._order(
            order_direction=OrderDirection.SELL,
            order_division=overseas_order.OverseasOrderDivision.MOC,
            exchange_code=exchange_code,
            ticker=ticker,
            quantity=quantity,
            price="0",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/hantu/test_overseas_api_order_loc_moc.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint + type check**

Run: `uv run ruff check src/hantu/ tests/hantu/test_overseas_api_order_loc_moc.py && uv run mypy src/hantu/`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/hantu/overseas_api.py tests/hantu/test_overseas_api_order_loc_moc.py
git commit -m "feat(hantu): add LOC/MOC overseas order methods for infinite-buying"
```

---

## Task 2: 체결조회(`inquire-ccnl`) 모델 + 메서드

**Files:**
- Create: `src/hantu/model/overseas/execution.py`
- Modify: `src/hantu/overseas_api.py` (`inquire_ccnl` + `_inquire_ccnl_recursive` 추가; import 추가)
- Test: `tests/hantu/test_overseas_api_inquire_ccnl.py`

**Interfaces:**
- Produces (`src.hantu.model.overseas.execution`):
  - `RequestHeader`, `RequestQueryParam`, `ExecutionRecord`, `ResponseBody`
  - `ExecutionRecord` 필드: `ord_dt:str`, `odno:str`, `pdno:str`, `sll_buy_dvsn_cd:str`, `ft_ord_qty:str`, `ft_ccld_qty:str`, `ft_ccld_unpr3:str`, `nccs_qty:str`, `prcs_stat_name:str`, `ord_tmd:str`, `ovrs_excg_cd:str`
- Produces (`HantuOverseasAPI`):
  - `inquire_ccnl(start_date: str, end_date: str, exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD, sell_buy_dvsn: str = "00", ccld_dvsn: str = "00", symbol: str = "%") -> list[execution.ExecutionRecord]` — 기간 내 전 페이지 체결/주문 내역(연속조회 누적).

- [ ] **Step 1: Write the failing test**

Create `tests/hantu/test_overseas_api_inquire_ccnl.py`:

```python
"""HantuOverseasAPI 체결조회(inquire-ccnl) 테스트 (requests mock)."""

from src.config import HantuConfig
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.model.overseas.exchange_code import OverseasExchangeCode
from src.hantu.overseas_api import HantuOverseasAPI


def _record(odno: str, pdno: str, ccld_qty: str, nccs_qty: str, sll_buy: str) -> dict:
    return {
        "ord_dt": "20260619", "odno": odno, "pdno": pdno,
        "sll_buy_dvsn_cd": sll_buy, "ft_ord_qty": "4",
        "ft_ccld_qty": ccld_qty, "ft_ccld_unpr3": "50.00", "nccs_qty": nccs_qty,
        "prcs_stat_name": "체결", "ord_tmd": "092000", "ovrs_excg_cd": "NASD",
    }


def _resp(mocker, tr_cont: str, output: list[dict], fk: str = "", nk: str = ""):
    res = mocker.Mock()
    res.status_code = 200
    res.headers = {"tr_cont": tr_cont}
    res.json.return_value = {
        "rt_cd": "0", "msg_cd": "MCA00000", "msg1": "정상처리 되었습니다.",
        "ctx_area_fk200": fk, "ctx_area_nk200": nk, "output": output,
    }
    return res


def test_inquire_ccnl_single_page_parses_records(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    res = _resp(mocker, "D", [_record("0030000123", "TQQQ", "4", "0", "02")])
    get = mocker.patch("requests.get", return_value=res)

    records = api.inquire_ccnl("20260619", "20260619", OverseasExchangeCode.NASD)

    assert len(records) == 1
    r = records[0]
    assert r.odno == "0030000123" and r.pdno == "TQQQ"
    assert r.ft_ccld_qty == "4" and r.nccs_qty == "0" and r.sll_buy_dvsn_cd == "02"
    # 실전 TR_ID
    assert get.call_args.kwargs["headers"]["tr_id"] == "TTTS3035R"
    params = get.call_args.kwargs["params"]
    assert params["ORD_STRT_DT"] == "20260619" and params["ORD_END_DT"] == "20260619"
    assert params["OVRS_EXCG_CD"] == "NASD"


def test_inquire_ccnl_follows_continuation(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    first = _resp(mocker, "M", [_record("0030000123", "TQQQ", "2", "2", "02")], fk="FK1", nk="NK1")
    second = _resp(mocker, "D", [_record("0030000999", "SOXL", "3", "0", "01")])
    get = mocker.patch("requests.get")
    get.side_effect = [first, second]

    records = api.inquire_ccnl("20260619", "20260619", OverseasExchangeCode.NASD)

    assert [r.odno for r in records] == ["0030000123", "0030000999"]
    assert get.call_count == 2
    second_params = get.call_args_list[1].kwargs["params"]
    assert second_params["CTX_AREA_FK200"] == "FK1"
    assert second_params["CTX_AREA_NK200"] == "NK1"


def test_inquire_ccnl_uses_virtual_tr_id(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.VIRTUAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    res = _resp(mocker, "D", [])
    get = mocker.patch("requests.get", return_value=res)

    api.inquire_ccnl("20260619", "20260619", OverseasExchangeCode.NASD)

    assert get.call_args.kwargs["headers"]["tr_id"] == "VTTS3035R"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hantu/test_overseas_api_inquire_ccnl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.hantu.model.overseas.execution'`

- [ ] **Step 3: Create the execution model**

Create `src/hantu/model/overseas/execution.py`:

```python
"""해외주식 주문체결내역 조회(inquire-ccnl) 모델.

명세 근거: open-trading-api/legacy/Sample01/kis_ovrseastk.py(get_overseas_inquire_ccnl),
examples_llm/overseas_stock/inquire_ccnl/. 단일 output 리스트.
"""

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    """체결조회 요청 헤더."""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str
    tr_cont: str = ""


class RequestQueryParam(BaseModel):
    """체결조회 요청 쿼리 파라미터 (대문자 그대로)."""

    CANO: str
    ACNT_PRDT_CD: str
    PDNO: str = "%"
    ORD_STRT_DT: str
    ORD_END_DT: str
    SLL_BUY_DVSN: str = "00"      # 00:전체 01:매도 02:매수
    CCLD_NCCS_DVSN: str = "00"    # 00:전체 01:체결 02:미체결
    OVRS_EXCG_CD: str = "%"
    SORT_SQN: str = "DS"          # DS:정순 (모의투자 미사용 → "")
    ORD_DT: str = ""
    ORD_GNO_BRNO: str = ""
    ODNO: str = ""
    CTX_AREA_FK200: str = ""
    CTX_AREA_NK200: str = ""


class ExecutionRecord(BaseModel):
    """체결/주문 내역 1건 (output)."""

    ord_dt: str = Field(default="", description="주문일자 YYYYMMDD")
    odno: str = Field(description="주문번호")
    pdno: str = Field(default="", description="종목코드")
    sll_buy_dvsn_cd: str = Field(default="", description="매도매수구분 01:매도 02:매수")
    ft_ord_qty: str = Field(default="0", description="주문수량")
    ft_ccld_qty: str = Field(default="0", description="체결수량")
    ft_ccld_unpr3: str = Field(default="0", description="체결단가")
    nccs_qty: str = Field(default="0", description="미체결수량")
    prcs_stat_name: str = Field(default="", description="처리상태명")
    ord_tmd: str = Field(default="", description="주문시각 HHMMSS")
    ovrs_excg_cd: str = Field(default="", description="해외거래소코드")


class ResponseBody(BaseModel):
    """체결조회 응답 전체 (단일 output 리스트 + 연속조회 키)."""

    rt_cd: str
    msg_cd: str
    msg1: str
    ctx_area_fk200: str = ""
    ctx_area_nk200: str = ""
    output: list[ExecutionRecord] = Field(default_factory=list)
```

- [ ] **Step 4: Add the `inquire_ccnl` method**

In `src/hantu/overseas_api.py`, add the import near the other overseas model imports (after line 12 `from src.hantu.model.overseas import order as overseas_order`):

```python
from src.hantu.model.overseas import execution as overseas_execution
```

Then add these methods to `HantuOverseasAPI` (place after `get_balance`/`_get_balance_recursive`, before `get_current_price` at line 133):

```python
    def inquire_ccnl(
            self,
            start_date: str,
            end_date: str,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD,
            sell_buy_dvsn: str = "00",
            ccld_dvsn: str = "00",
            symbol: str = "%",
    ) -> list[overseas_execution.ExecutionRecord]:
        """해외주식 주문체결내역 조회 (기간 내 전 페이지 누적).

        Args:
            start_date: 조회 시작일 YYYYMMDD (현지시각 기준)
            end_date: 조회 종료일 YYYYMMDD
            exchange_code: 거래소코드 (기본 NASD)
            sell_buy_dvsn: 00:전체 01:매도 02:매수 (모의투자는 00)
            ccld_dvsn: 00:전체 01:체결 02:미체결 (모의투자는 00)
            symbol: 종목코드, "%"는 전종목

        Returns:
            ExecutionRecord 리스트 (주문번호 odno로 우리가 낸 주문과 대조).
        """
        return self._inquire_ccnl_recursive(
            start_date=start_date, end_date=end_date, exchange_code=exchange_code,
            sell_buy_dvsn=sell_buy_dvsn, ccld_dvsn=ccld_dvsn, symbol=symbol,
        )

    def _inquire_ccnl_recursive(
            self,
            start_date: str,
            end_date: str,
            exchange_code: OverseasExchangeCode,
            sell_buy_dvsn: str,
            ccld_dvsn: str,
            symbol: str,
            ctx_area_fk200: str = "",
            ctx_area_nk200: str = "",
            continuation_flag: str = "",
            accumulated: list[overseas_execution.ExecutionRecord] | None = None,
    ) -> list[overseas_execution.ExecutionRecord]:
        """체결조회 연속조회(내부). tr_cont M/F면 다음 페이지를 이어 받는다(잔고조회와 동형)."""
        if accumulated is None:
            accumulated = []

        url = f"{self.url_base}/uapi/overseas-stock/v1/trading/inquire-ccnl"
        tr_id = "TTTS3035R" if self.account_type == AccountType.REAL else "VTTS3035R"
        # 모의투자는 SORT_SQN 미지원
        sort_sqn = "DS" if self.account_type == AccountType.REAL else ""

        header = overseas_execution.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=tr_id,
            tr_cont=continuation_flag,
        )
        param = overseas_execution.RequestQueryParam(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd,
            PDNO=symbol,
            ORD_STRT_DT=start_date,
            ORD_END_DT=end_date,
            SLL_BUY_DVSN=sell_buy_dvsn,
            CCLD_NCCS_DVSN=ccld_dvsn,
            OVRS_EXCG_CD=exchange_code.value,
            SORT_SQN=sort_sqn,
            CTX_AREA_FK200=ctx_area_fk200,
            CTX_AREA_NK200=ctx_area_nk200,
        )

        res = requests.get(url, headers=header.model_dump(by_alias=True), params=param.model_dump())
        self._validate_response(res)
        body = overseas_execution.ResponseBody.model_validate(res.json())
        accumulated.extend(body.output)

        if res.headers.get("tr_cont", "") in ["M", "F"]:
            time.sleep(0.1)
            return self._inquire_ccnl_recursive(
                start_date=start_date, end_date=end_date, exchange_code=exchange_code,
                sell_buy_dvsn=sell_buy_dvsn, ccld_dvsn=ccld_dvsn, symbol=symbol,
                ctx_area_fk200=body.ctx_area_fk200, ctx_area_nk200=body.ctx_area_nk200,
                continuation_flag="N", accumulated=accumulated,
            )
        return accumulated
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/hantu/test_overseas_api_inquire_ccnl.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Lint + type check**

Run: `uv run ruff check src/hantu/ tests/hantu/test_overseas_api_inquire_ccnl.py && uv run mypy src/hantu/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/hantu/model/overseas/execution.py src/hantu/overseas_api.py tests/hantu/test_overseas_api_inquire_ccnl.py
git commit -m "feat(hantu): add overseas execution inquiry (inquire-ccnl) for fill reconciliation"
```

---

## Self-Review Notes

- **Spec coverage (Phase 2b 범위):** v1 발주에 필요한 LOC 매수/매도, MOC 매도(Task 1) + 대조잡이 쓸 체결조회(Task 2). LIMIT 매도는 기존 `sell_limit_order` 재사용(추가 불필요). 매수 MOC는 미국에서 불가(enum 주석)이고 order_plan도 매수는 LOC만 내므로 미추가(YAGNI).
- **명세 근거:** TR_ID(TTTT1002U/TTTT1006U/TTTS3035R/VTTS3035R), ORD_DVSN(34/33), 응답 필드(odno/ft_ccld_qty/ft_ccld_unpr3/nccs_qty/sll_buy_dvsn_cd)는 기존 코드·번들 예제에서 확정. 추측 없음.
- **패턴 일치:** `inquire_ccnl`은 `get_balance`/`_get_balance_recursive`와 동형(GET+헤더 tr_cont+연속조회 ctx_area). 주문 래퍼는 `buy_limit_order`와 동형(`_order` 위임).
- **Type consistency:** `ExecutionRecord.odno`/`ft_ccld_qty`/`ft_ccld_unpr3`/`sll_buy_dvsn_cd`는 Phase 2c 대조잡이 우리 `InfiniteBuyingOrder.kis_order_no`와 매칭하고 `filled_qty`/`filled_price`/`status`를 채우는 데 쓰인다. `OrderOutput.ODNO`(주문 응답) → `InfiniteBuyingOrder.kis_order_no` 저장 경로도 Phase 2c.
- **테스트:** 모두 `requests`/`_get_token` mock(기존 패턴), 실거래 호출 없음. 모의투자(LIMIT만 가능) 제약상 LOC/MOC 실체결 검증은 불가하므로 요청 바디·TR_ID·응답 파싱으로 검증.
- **경계(Phase 2c):** intent→KIS 발주 매핑, 주문번호 원장 기록, 체결조회 결과로 평단·T·사이클 갱신(position_math 재사용), ET 스케줄, config CRUD API는 범위 밖.
- **알려진 한계:** 주문 정정/취소 미구현(v1 fire-and-forget이라 불필요); AFTER지정가/주간거래 미구현(스펙 §10).
