"""예탁원정보(배당일정) ksdinfo_dividend 모델."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DividendKind(str, Enum):
    """조회 구분 (KIS GB1)."""

    ALL = "0"      # 배당 전체
    SETTLE = "1"   # 결산 배당
    INTERIM = "2"  # 중간/분기 배당


class RequestHeader(BaseModel):
    """요청 헤더"""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "HHKDB669102C0"
    tr_cont: str = ""
    custtype: str | None = None


class RequestQueryParam(BaseModel):
    """요청 쿼리 파라미터"""

    CTS: str = ""        # 연속 조회 키 (최초 호출 시 공백)
    GB1: str             # 0: 전체, 1: 결산, 2: 중간
    F_DT: str            # 조회 시작 YYYYMMDD
    T_DT: str            # 조회 종료 YYYYMMDD
    SHT_CD: str = ""     # 종목코드 (공백 = 전체)
    HIGH_GB: str = ""    # 고배당 여부 (사용 안 함)


class DividendOutput(BaseModel):
    """배당 일정 단건. KIS 응답 필드 일부만 매핑하고 나머지는 무시."""

    model_config = ConfigDict(extra="ignore")

    sht_cd: str = Field(description="종목코드")
    isin_name: str | None = Field(default=None, description="종목명")
    record_date: str | None = Field(default=None, description="기준일 YYYYMMDD")
    divi_pay_dt: str | None = Field(default=None, description="배당지급일 YYYYMMDD")
    per_sto_divi_amt: str | None = Field(default=None, description="1주당 배당금")
    divi_rate: str | None = Field(default=None, description="시가배당률(%)")
    stk_divi_rate: str | None = Field(default=None, description="주식배당률")
    divi_kind: str | None = Field(default=None, description="배당 종류")
    divi_aplc_yymm: str | None = Field(default=None, description="배당기준연월 YYYYMM")


class ResponseBody(BaseModel):
    """API 응답 바디"""

    model_config = ConfigDict(extra="ignore")

    rt_cd: str = Field(description="성공 실패 여부 (0:성공)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output1: list[DividendOutput] = Field(default_factory=list, description="배당 일정 목록")
    cts: str | None = Field(default=None, description="다음 페이지 연속 조회 키")
