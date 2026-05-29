"""KIS 국내주식 손익계산서(finance/income-statement) 모델.

TR_ID: FHKST66430200 — 실전/모의 동일. 단일 호출에 전체 이력(연간 20여 년·분기 30여 기)
반환하며 tr_cont 연속조회 불필요(실측 2026-05-29).

금액 단위 = 억원(실측: 삼성전자 202312 sale_account="2589355.00" = 258.94조 = 공시 일치).
값은 문자열("2589355.00"), 적자는 음수("-1062.00"). 미제공 필드는 "99.99" sentinel로 옴
(depr_cost/sell_mang/bsop_non_*/spec_* 등) → 호출자가 None 처리. 분기는 연단위 누적합산.
"""

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    """요청 헤더."""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "FHKST66430200"
    custtype: str = "P"


class RequestQueryParam(BaseModel):
    """요청 쿼리 파라미터 (KIS 키 케이싱 그대로)."""

    FID_DIV_CLS_CODE: str  # 0: 년, 1: 분기(연단위 누적합산)
    fid_cond_mrkt_div_code: str = "J"  # 시장 분류 코드
    fid_input_iscd: str  # 종목코드 (6자리)


class IncomeStatementOutput(BaseModel):
    """손익계산서 응답 output 1건 — 신뢰 가능 필드만 표면화.

    KIS는 미제공 필드를 "99.99"로 채우므로(depr_cost/sell_mang/bsop_non_*/spec_*),
    실측상 실값이 오는 필드만 선언한다. 나머지는 무시(BaseModel 기본).
    """

    stac_yymm: str | None = Field(default=None, description="결산년월 YYYYMM")
    sale_account: str | None = Field(default=None, description="매출액(억원)")
    sale_cost: str | None = Field(default=None, description="매출원가(억원)")
    sale_totl_prfi: str | None = Field(default=None, description="매출총이익(억원)")
    bsop_prti: str | None = Field(default=None, description="영업이익(억원)")
    op_prfi: str | None = Field(default=None, description="경상이익(억원)")
    thtr_ntin: str | None = Field(default=None, description="당기순이익(억원)")


class ResponseBody(BaseModel):
    """API 응답 바디."""

    rt_cd: str = Field(description="성공 실패 여부 (0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output: list[IncomeStatementOutput] = Field(default_factory=list, description="결산기별 손익계산서")
