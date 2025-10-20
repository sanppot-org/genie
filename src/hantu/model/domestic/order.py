"""주식 주문 관련 모델"""

from enum import Enum

from pydantic import BaseModel, Field


class OrderDivision(str, Enum):
    """주문 구분"""

    LIMIT = "00"  # 지정가
    MARKET = "01"  # 시장가


class RequestHeader(BaseModel):
    """주문 요청 헤더"""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str  # 거래ID (TTTC0011U/VTTC0011U: 매도, TTTC0012U/VTTC0012U: 매수)
    custtype: str | None = None
    personalseckey: str | None = None


class RequestBody(BaseModel):
    """주문 요청 바디"""

    CANO: str = Field(description="종합계좌번호")
    ACNT_PRDT_CD: str = Field(description="계좌상품코드")
    PDNO: str = Field(description="상품번호(종목코드)")
    ORD_DVSN: str = Field(description="주문구분(00:지정가, 01:시장가, 등)")
    ORD_QTY: str = Field(description="주문수량")
    ORD_UNPR: str = Field(description="주문단가(시장가는 0)")
    EXCG_ID_DVSN_CD: str = Field(default="KRX", description="거래소ID구분코드")
    SLL_TYPE: str = Field(default="", description="매도유형(01:일반매도,02:임의매매,05:대차매도)")
    CNDT_PRIC: str = Field(default="", description="조건가격(스탑지정가 시 사용)")


class OrderOutput(BaseModel):
    """주문 응답 output"""

    KRX_FWDG_ORD_ORGNO: str = Field(description="한국거래소전송주문조직번호")
    ODNO: str = Field(description="주문번호")
    ORD_TMD: str = Field(description="주문시각")


class ResponseBody(BaseModel):
    """주문 응답 전체"""

    rt_cd: str = Field(description="성공 실패 여부(0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output: OrderOutput = Field(description="응답 상세")
