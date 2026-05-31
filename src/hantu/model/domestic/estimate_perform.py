"""KIS 국내주식 종목추정실적(quotations/estimate-perform) 모델.

TR_ID: HHKST668300C0 — 입력 SHT_CD(종목코드) 단건. 증권사 컨센서스(FnGuide 계열) 추정실적.
실측(2026-05-31) 응답 구조:
- output1: 종목 기본정보 + 최근 리포트(애널리스트/추정일/투자의견)
- output2: 6행 × data1~5 = [매출액, 매출증가율, 영업이익, 영업이익증가율, 순이익, 순이익증가율]
- output3: 8행 × data1~5 = [EBITDA, EPS, EPS증가율, PER, EV/EBITDA, ROE, 부채비율, (미상)]
- output4: 기간 5개 (예: '2023.12','2024.12','2025.12','2026.12E','2027.12E') — 'E' suffix=추정.

data 열(data1~5) ↔ output4 기간 1:1 매핑. 금액 단위 억원(손익계산서와 동일),
증가율/비율/EPS/PER은 ×10(소수 1자리). 미커버 종목은 rt_cd=0이나 output 전부 빈 응답.
"""

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    """요청 헤더."""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "HHKST668300C0"
    custtype: str = "P"


class RequestQueryParam(BaseModel):
    """요청 쿼리 파라미터."""

    SHT_CD: str  # 종목코드 (6자리)


class EstimateDataRow(BaseModel):
    """output2/output3 1행 — data1~5는 output4 기간과 1:1 매핑되는 지표 값(문자열)."""

    data1: str | None = None
    data2: str | None = None
    data3: str | None = None
    data4: str | None = None
    data5: str | None = None


class EstimatePeriodRow(BaseModel):
    """output4 1행 — 기간(결산년월). 'E' suffix는 추정 기간."""

    dt: str | None = Field(default=None, description="결산년월 'YYYY.MM' 또는 'YYYY.MME'(추정)")


class ResponseBody(BaseModel):
    """API 응답 바디. 미커버 종목은 output* 빈 리스트."""

    rt_cd: str = Field(description="성공 실패 여부 (0:성공)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output2: list[EstimateDataRow] = Field(default_factory=list, description="손익 추정 6행")
    output3: list[EstimateDataRow] = Field(default_factory=list, description="비율/밸류 추정 8행")
    output4: list[EstimatePeriodRow] = Field(default_factory=list, description="기간 5개")
