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
