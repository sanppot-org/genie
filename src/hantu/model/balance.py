from typing import Optional, List

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")  # 컨텐츠타입
    authorization: str  # 접근토큰
    appkey: str  # 앱키
    appsecret: str  # 앱시크릿키
    personalseckey: Optional[str] = None  # 고객식별키
    tr_id: str  # 거래ID
    tr_cont: Optional[str] = None  # 연속 거래 여부
    custtype: Optional[str] = None  # 고객타입
    seq_no: Optional[str] = None  # 일련번호
    mac_address: Optional[str] = None  # 맥주소
    phone_number: Optional[str] = None  # 핸드폰번호
    ip_addr: Optional[str] = None  # 접속 단말 공인 IP
    gt_uid: Optional[str] = None  # Global UID


class RequestQueryParam(BaseModel):
    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드
    AFHR_FLPR_YN: str = 'N'  # 시간외단일가, 거래소여부 [N:기본값, Y:시간외단일가, X: NXT 정규장]
    OFL_YN: str = ''  # 오프라인여부
    INQR_DVSN: str = '02'  # 조회구분 [01:대출일별, 02:종목별]
    UNPR_DVSN: str = '01'  # 단가구분
    FUND_STTL_ICLD_YN: str = 'N'  # 펀드결제분포함여부 [N, Y]
    FNCG_AMT_AUTO_RDPT_YN: str = 'N'  # 융자금액자동상환여부
    PRCS_DVSN: str = '01'  # 처리구분 [00:전일매매포함, 01:전일매매미포함]
    CTX_AREA_FK100: str = ''  # 연속조회검색조건100
    CTX_AREA_NK100: str = ''  # 연속조회키100


class ResponseHeader(BaseModel):
    content_type: str = Field(alias="Content-Type")  # 컨텐츠타입
    tr_id: str  # 거래ID
    tr_cont: str  # 연속 거래 여부
    gt_uid: str  # Global UID


class ResponseBodyoutput1(BaseModel):
    pdno: str  # 상품번호
    prdt_name: str  # 상품명
    trad_dvsn_name: str  # 매매구분명
    bfdy_buy_qty: str  # 전일매수수량
    bfdy_sll_qty: str  # 전일매도수량
    thdt_buyqty: str  # 금일매수수량
    thdt_sll_qty: str  # 금일매도수량
    hldg_qty: str  # 보유수량
    ord_psbl_qty: str  # 주문가능수량
    pchs_avg_pric: str  # 매입평균가격
    pchs_amt: str  # 매입금액
    prpr: str  # 현재가
    evlu_amt: str  # 평가금액
    evlu_pfls_amt: str  # 평가손익금액
    evlu_pfls_rt: str  # 평가손익율
    evlu_erng_rt: str  # 평가수익율
    loan_dt: str  # 대출일자
    loan_amt: str  # 대출금액
    stln_slng_chgs: str  # 대주매각대금
    expd_dt: str  # 만기일자
    fltt_rt: str  # 등락율
    bfdy_cprs_icdc: str  # 전일대비증감
    item_mgna_rt_name: str  # 종목증거금율명
    grta_rt_name: str  # 보증금율명
    sbst_pric: str  # 대용가격
    stck_loan_unpr: str  # 주식대출단가


class ResponseBodyoutput2(BaseModel):
    dnca_tot_amt: str  # 예수금총금액
    nxdy_excc_amt: str  # 익일정산금액
    prvs_rcdl_excc_amt: str  # 가수도정산금액
    cma_evlu_amt: str  # CMA평가금액
    bfdy_buy_amt: str  # 전일매수금액
    thdt_buy_amt: str  # 금일매수금액
    nxdy_auto_rdpt_amt: str  # 익일자동상환금액
    bfdy_sll_amt: str  # 전일매도금액
    thdt_sll_amt: str  # 금일매도금액
    d2_auto_rdpt_amt: str  # D+2자동상환금액
    bfdy_tlex_amt: str  # 전일제비용금액
    thdt_tlex_amt: str  # 금일제비용금액
    tot_loan_amt: str  # 총대출금액
    scts_evlu_amt: str  # 유가평가금액
    tot_evlu_amt: str  # 총평가금액
    nass_amt: str  # 순자산금액
    fncg_gld_auto_rdpt_yn: str  # 융자금자동상환여부
    pchs_amt_smtl_amt: str  # 매입금액합계금액
    evlu_amt_smtl_amt: str  # 평가금액합계금액
    evlu_pfls_smtl_amt: str  # 평가손익합계금액
    tot_stln_slng_chgs: str  # 총대주매각대금
    bfdy_tot_asst_evlu_amt: str  # 전일총자산평가금액
    asst_icdc_amt: str  # 자산증감액
    asst_icdc_erng_rt: str  # 자산증감수익율


class ResponseBody(BaseModel):
    rt_cd: str  # 성공 실패 여부
    msg_cd: str  # 응답코드
    msg1: str  # 응답메세지
    ctx_area_fk100: str  # 연속조회검색조건100
    ctx_area_nk100: str  # 연속조회키100
    output1: List[ResponseBodyoutput1] = []  # 응답상세1
    output2: List[ResponseBodyoutput2] = []  # 응답상세2
