"""해외주식 주문 관련 모델"""

from enum import Enum

from pydantic import BaseModel, Field


class OverseasOrderDivision(str, Enum):
    """해외주식 주문 구분

    미국(NASD/NYSE/AMEX):
        - 매수: 00(지정가), 32(LOO 장개시지정가), 34(LOC 장마감지정가)
        - 매도: 00(지정가), 31(MOO 장개시시장가), 32(LOO 장개시지정가), 33(MOC 장마감시장가), 34(LOC 장마감지정가)
        * 모의투자는 00(지정가)만 가능

    홍콩(SEHK):
        - 매수: 00(지정가), 32(LOO 장개시지정가), 34(LOC 장마감지정가)
        - 매도: 00(지정가), 50(단주지정가)
        * 모의투자는 00(지정가)만 가능

    기타 거래소:
        - 00(지정가)
    """

    LIMIT = "00"  # 지정가
    MOO = "31"  # 장개시시장가 (미국 매도만)
    LOO = "32"  # 장개시지정가 (미국)
    MOC = "33"  # 장마감시장가 (미국 매도만)
    LOC = "34"  # 장마감지정가 (미국)
    FRACTIONAL_LIMIT = "50"  # 단주지정가 (홍콩 매도만)


class RequestHeader(BaseModel):
    """해외주식 주문 요청 헤더"""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str  # 거래소 및 매수/매도에 따라 다름
    custtype: str | None = None
    personalseckey: str | None = None


class RequestBody(BaseModel):
    """해외주식 주문 요청 바디"""

    CANO: str = Field(description="종합계좌번호")
    ACNT_PRDT_CD: str = Field(description="계좌상품코드")
    OVRS_EXCG_CD: str = Field(description="해외거래소코드 (NASD/NYSE/AMEX/SEHK/SHAA/SZAA/TKSE/HASE/VNSE)")
    PDNO: str = Field(description="상품번호(종목코드)")
    ORD_QTY: str = Field(description="주문수량")
    OVRS_ORD_UNPR: str = Field(description="해외주문단가 (시장가는 0)")
    CTAC_TLNO: str = Field(default="", description="연락전화번호")
    MGCO_APTM_ODNO: str = Field(default="", description="운용사지정주문번호")
    SLL_TYPE: str = Field(default="", description="매도유형 (매도: 00, 매수: 빈 문자열)")
    ORD_SVR_DVSN_CD: str = Field(default="0", description="주문서버구분코드")
    ORD_DVSN: str = Field(description="주문구분 (00:지정가 등)")


class OrderOutput(BaseModel):
    """해외주식 주문 응답 output"""

    KRX_FWDG_ORD_ORGNO: str = Field(description="한국거래소전송주문조직번호")
    ODNO: str = Field(description="주문번호")
    ORD_TMD: str = Field(description="주문시각")


class ResponseBody(BaseModel):
    """해외주식 주문 응답 전체"""

    rt_cd: str = Field(description="성공 실패 여부(0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output: OrderOutput = Field(description="응답 상세")
