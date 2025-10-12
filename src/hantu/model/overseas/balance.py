from typing import List, Optional

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str
    tr_cont: str = ""
    custtype: Optional[str] = None
    personalseckey: Optional[str] = None
    seq_no: Optional[str] = None
    mac_address: Optional[str] = None
    phone_number: Optional[str] = None
    ip_addr: Optional[str] = None
    gt_uid: Optional[str] = None


class RequestQueryParam(BaseModel):
    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드
    OVRS_EXCG_CD: str  # 해외거래소코드 (NASD, NYSE, AMEX, SEHK, SHAA, SZAA, TKSE, HASE, VNSE)
    TR_CRCY_CD: str  # 거래통화코드 (USD, HKD, CNY, JPY, VND)
    CTX_AREA_FK200: str = ""  # 연속조회검색조건200
    CTX_AREA_NK200: str = ""  # 연속조회키200


class ResponseHeader(BaseModel):
    content_type: str = Field(alias="Content-Type")
    tr_id: str
    tr_cont: str
    gt_uid: str


class ResponseBodyoutput1(BaseModel):
    """개별 종목 보유 정보"""
    cano: str = ""  # 종합계좌번호
    acnt_prdt_cd: str = ""  # 계좌상품코드
    prdt_type_cd: str = ""  # 상품유형코드
    ovrs_pdno: str = ""  # 해외상품번호
    ovrs_item_name: str = ""  # 해외종목명
    frcr_evlu_pfls_amt: str = ""  # 외화평가손익금액
    evlu_pfls_rt: str = ""  # 평가손익율
    pchs_avg_pric: str = ""  # 매입평균가격
    ovrs_cblc_qty: str = ""  # 해외잔고수량
    ord_psbl_qty: str = ""  # 주문가능수량
    frcr_pchs_amt1: str = ""  # 외화매입금액1
    ovrs_stck_evlu_amt: str = ""  # 해외주식평가금액
    now_pric2: str = ""  # 현재가격2
    tr_crcy_cd: str = ""  # 거래통화코드
    ovrs_excg_cd: str = ""  # 해외거래소코드
    loan_type_cd: str = ""  # 대출유형코드
    loan_dt: str = ""  # 대출일자
    expd_dt: str = ""  # 만기일자


class ResponseBodyoutput2(BaseModel):
    """계좌 전체 정보"""
    frcr_pchs_amt1: str = ""  # 외화매입금액1
    ovrs_rlzt_pfls_amt: str = ""  # 해외실현손익금액
    ovrs_tot_pfls: str = ""  # 해외총손익
    rlzt_erng_rt: str = ""  # 실현수익율
    tot_evlu_pfls_amt: str = ""  # 총평가손익금액
    tot_pftrt: str = ""  # 총수익률
    frcr_buy_amt_smtl1: str = ""  # 외화매수금액합계1
    ovrs_rlzt_pfls_amt2: str = ""  # 해외실현손익금액2
    frcr_buy_amt_smtl2: str = ""  # 외화매수금액합계2


class ResponseBody(BaseModel):
    rt_cd: str  # 성공 실패 여부
    msg_cd: str  # 응답코드
    msg1: str  # 응답메세지
    ctx_area_fk200: str = ""  # 연속조회검색조건200
    ctx_area_nk200: str = ""  # 연속조회키200
    output1: List[ResponseBodyoutput1] = []  # 응답상세1 (개별 종목)
    output2: ResponseBodyoutput2  # 응답상세2 (계좌 전체)


class OverseasBalanceResponse(BaseModel):
    """해외 주식 잔고 조회 전체 응답

    연속 조회를 통해 수집된 전체 잔고 정보
    """
    output1: List[ResponseBodyoutput1] = []  # 개별 종목 보유 정보
    output2: ResponseBodyoutput2  # 계좌 전체 정보
