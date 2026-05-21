"""KIS 주식기본조회(search-stock-info) 모델.

TR_ID: CTPF1002R — 실전/모의 동일. ETF/ETN/ELW도 PRDT_TYPE_CD=300으로 호출 가능
하지만 ETF는 업종/섹터 필드가 비어 오는 경우가 있어 호출자가 None 처리한다.
"""

from pydantic import BaseModel, Field


class RequestHeader(BaseModel):
    """요청 헤더."""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "CTPF1002R"
    custtype: str | None = None


class RequestQueryParam(BaseModel):
    """요청 쿼리 파라미터."""

    PRDT_TYPE_CD: str  # 300: 주식/ETF/ETN/ELW
    PDNO: str  # 종목번호 (6자리)


class SearchStockInfoOutput(BaseModel):
    """주식기본조회 응답 output — 업종/섹터 필드만 표면화.

    응답에는 70여 개 필드가 있으나 본 모듈은 업종 분류만 소비한다.
    나머지 필드는 무시(BaseModel 기본 동작) — 추가 필요 시 여기에 선언.
    """

    # 표준산업분류(KSIC)
    std_idst_clsf_cd: str | None = Field(default=None, description="표준산업분류코드")
    std_idst_clsf_cd_name: str | None = Field(default=None, description="표준산업분류코드명")

    # 지수업종 3단(증권업계 분류)
    idx_bztp_lcls_cd: str | None = Field(default=None, description="지수업종 대분류 코드")
    idx_bztp_lcls_cd_name: str | None = Field(default=None, description="지수업종 대분류 코드명")
    idx_bztp_mcls_cd: str | None = Field(default=None, description="지수업종 중분류 코드")
    idx_bztp_mcls_cd_name: str | None = Field(default=None, description="지수업종 중분류 코드명")
    idx_bztp_scls_cd: str | None = Field(default=None, description="지수업종 소분류 코드")
    idx_bztp_scls_cd_name: str | None = Field(default=None, description="지수업종 소분류 코드명")


class ResponseBody(BaseModel):
    """API 응답 바디."""

    rt_cd: str = Field(description="성공 실패 여부 (0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output: SearchStockInfoOutput = Field(description="응답 상세")
