"""주식 현재가 시세 조회 모델"""
from typing import Optional

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    """요청 헤더"""
    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "FHKST01010100"  # 실전/모의 동일
    custtype: Optional[str] = None


class RequestQueryParam(BaseModel):
    """요청 쿼리 파라미터"""
    FID_COND_MRKT_DIV_CODE: str  # 조건 시장 분류 코드 (J:KRX, NX:NXT, UN:통합)
    FID_INPUT_ISCD: str  # 종목코드


class StockPriceOutput(BaseModel):
    """주식 현재가 시세 응답 output

    주요 필드만 정의. 실제 API 응답에는 더 많은 필드가 포함됨.
    필요한 필드는 추가로 정의 가능.
    """
    # 기본 시세 정보
    stck_prpr: str = Field(description="주식 현재가")
    stck_oprc: str = Field(description="시가")
    stck_hgpr: str = Field(description="고가")
    stck_lwpr: str = Field(description="저가")
    stck_mxpr: str = Field(description="상한가")
    stck_llam: str = Field(description="하한가")
    stck_sdpr: str = Field(description="기준가")

    # 거래 정보
    acml_vol: str = Field(description="누적 거래량")
    acml_tr_pbmn: str = Field(description="누적 거래대금")

    # 전일 대비
    prdy_vrss: str = Field(description="전일 대비")
    prdy_vrss_sign: str = Field(description="전일 대비 부호")
    prdy_ctrt: str = Field(description="전일 대비율")

    # 추가 정보 (선택적)
    stck_prdy_clpr: Optional[str] = Field(default=None, description="전일 종가")
    hts_kor_isnm: Optional[str] = Field(default=None, description="HTS 한글 종목명")
    per: Optional[str] = Field(default=None, description="PER")
    pbr: Optional[str] = Field(default=None, description="PBR")
    eps: Optional[str] = Field(default=None, description="EPS")
    bps: Optional[str] = Field(default=None, description="BPS")


class ResponseBody(BaseModel):
    """API 응답 바디"""
    rt_cd: str = Field(description="성공 실패 여부 (0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output: StockPriceOutput = Field(description="응답 상세")
