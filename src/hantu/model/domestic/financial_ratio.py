"""KIS 국내주식 재무비율(finance/financial-ratio) 모델.

TR_ID: FHKST66430300 — 실전/모의 동일. 단일 호출에 결산기별 시계열 반환하며
tr_cont 연속조회 불필요(income-statement와 동일 구조).

값은 문자열(스케일 없는 % 또는 원 그대로, 예: roe_val="17.07"). 성장률은 음수 가능하며
적자지속/흑자전환/적자전환 등은 "0"으로 옴. 연간(FID_DIV_CLS_CODE="0")만 수집한다.
"""

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    """요청 헤더."""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "FHKST66430300"
    custtype: str = "P"


class RequestQueryParam(BaseModel):
    """요청 쿼리 파라미터 (KIS 키 케이싱 그대로)."""

    FID_DIV_CLS_CODE: str  # 0: 년 (연간만 수집)
    fid_cond_mrkt_div_code: str = "J"  # 시장 분류 코드
    fid_input_iscd: str  # 종목코드 (6자리)


class FinancialRatioOutput(BaseModel):
    """재무비율 응답 output 1건 — 모든 필드 문자열(스케일 없는 % 또는 원)."""

    stac_yymm: str | None = Field(default=None, description="결산년월 YYYYMM")
    grs: str | None = Field(default=None, description="매출액 증가율(%)")
    bsop_prfi_inrt: str | None = Field(default=None, description="영업이익 증가율(%)")
    ntin_inrt: str | None = Field(default=None, description="순이익 증가율(%)")
    roe_val: str | None = Field(default=None, description="ROE(%)")
    eps: str | None = Field(default=None, description="EPS(원)")
    sps: str | None = Field(default=None, description="주당매출액(원)")
    bps: str | None = Field(default=None, description="BPS(원)")
    rsrv_rate: str | None = Field(default=None, description="유보비율(%)")
    lblt_rate: str | None = Field(default=None, description="부채비율(%)")


class ResponseBody(BaseModel):
    """API 응답 바디."""

    rt_cd: str = Field(description="성공 실패 여부 (0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output: list[FinancialRatioOutput] = Field(default_factory=list, description="결산기별 재무비율")
