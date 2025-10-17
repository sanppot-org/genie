from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str
    custtype: str | None = None


class RequestQueryParam(BaseModel):
    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드
    PDNO: str  # 상품번호 (종목코드)
    ORD_UNPR: str  # 주문단가
    ORD_DVSN: str  # 주문구분 (00:지정가, 01:시장가)
    CMA_EVLU_AMT_ICLD_YN: str  # CMA평가금액포함여부
    OVRS_ICLD_YN: str  # 해외포함여부


class ResponseBodyOutput(BaseModel):
    ord_psbl_cash: str  # 주문가능현금
    ord_psbl_sbst: str  # 주문가능대용
    ruse_psbl_amt: str  # 재사용가능금액
    fund_rpch_chgs: str  # 펀드환매대금
    psbl_qty_calc_unpr: str  # 가능수량계산단가
    nrcvb_buy_amt: str  # 미수없는매수금액
    nrcvb_buy_qty: str  # 미수없는매수수량
    max_buy_amt: str  # 최대매수금액
    max_buy_qty: str  # 최대매수수량
    cma_evlu_amt: str  # CMA평가금액
    ovrs_re_use_amt_wcrc: str  # 해외재사용금액원화
    ord_psbl_frcr_amt_wcrc: str  # 주문가능외화금액원화


class ResponseBody(BaseModel):
    rt_cd: str  # 성공 실패 여부
    msg_cd: str  # 응답코드
    msg1: str  # 응답메세지
    output: ResponseBodyOutput
