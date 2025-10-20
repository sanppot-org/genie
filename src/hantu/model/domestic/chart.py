"""차트 조회 모델"""

from enum import Enum

from pydantic import BaseModel, Field

from src.hantu.model.domestic.market_code import MarketCode


class ChartInterval(str, Enum):
    """차트 주기"""

    DAY = "D"  # 일봉
    WEEK = "W"  # 주봉
    MONTH = "M"  # 월봉
    YEAR = "Y"  # 년봉


class PriceType(str, Enum):
    """가격 타입"""

    ADJUSTED = "0"  # 수정주가
    ORIGINAL = "1"  # 원주가


# ===== 일/주/월/년봉 조회 =====


class DailyChartRequestHeader(BaseModel):
    """일/주/월/년봉 요청 헤더"""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "FHKST03010100"  # 실전/모의 동일
    custtype: str | None = None


class DailyChartRequestQueryParam(BaseModel):
    """일/주/월/년봉 요청 쿼리 파라미터"""

    FID_COND_MRKT_DIV_CODE: MarketCode  # 조건 시장 분류 코드
    FID_INPUT_ISCD: str  # 종목코드
    FID_INPUT_DATE_1: str  # 조회 시작일자 (YYYYMMDD)
    FID_INPUT_DATE_2: str  # 조회 종료일자 (YYYYMMDD)
    FID_PERIOD_DIV_CODE: ChartInterval  # 기간분류코드
    FID_ORG_ADJ_PRC: PriceType  # 수정주가 원주가 가격 여부


class DailyChartOutput1(BaseModel):
    """일/주/월/년봉 output1 (전체 정보)"""

    # 전일 대비
    prdy_vrss: str = Field(description="전일 대비")
    prdy_vrss_sign: str = Field(description="전일 대비 부호")
    prdy_ctrt: str = Field(description="전일 대비율")

    # 기본 정보
    stck_prdy_clpr: str = Field(description="주식 전일 종가")
    acml_vol: str = Field(description="누적 거래량")
    acml_tr_pbmn: str = Field(description="누적 거래대금")
    hts_kor_isnm: str = Field(description="HTS 한글 종목명")
    stck_prpr: str = Field(description="주식 현재가")
    stck_shrn_iscd: str = Field(description="주식 단축 종목코드")
    prdy_vol: str = Field(description="전일 거래량")

    # 가격 정보
    stck_mxpr: str = Field(description="상한가")
    stck_llam: str = Field(description="하한가")
    stck_oprc: str = Field(description="시가")
    stck_hgpr: str = Field(description="최고가")
    stck_lwpr: str = Field(description="최저가")
    stck_prdy_oprc: str = Field(description="전일 시가")
    stck_prdy_hgpr: str = Field(description="전일 최고가")
    stck_prdy_lwpr: str = Field(description="전일 최저가")

    # 호가 정보
    askp: str = Field(description="매도호가")
    bidp: str = Field(description="매수호가")
    prdy_vrss_vol: str = Field(description="전일 대비 거래량")
    vol_tnrt: str = Field(description="거래량 회전율")

    # 종목 정보
    stck_fcam: str = Field(description="액면가")
    lstn_stcn: str = Field(description="상장 주수")
    cpfn: str = Field(description="자본금")
    hts_avls: str = Field(description="시가총액")

    # 재무 정보
    per: str = Field(description="PER")
    eps: str = Field(description="EPS")
    pbr: str = Field(description="PBR")
    itewhol_loan_rmnd_ratem: str = Field(description="전체 융자 잔고 비율", alias="itewhol_loan_rmnd_ratem name")


class DailyChartOutput2(BaseModel):
    """일/주/월/년봉 output2 (개별 봉 데이터)"""

    stck_bsop_date: str = Field(description="영업 일자")
    stck_clpr: str = Field(description="종가")
    stck_oprc: str = Field(description="시가")
    stck_hgpr: str = Field(description="최고가")
    stck_lwpr: str = Field(description="최저가")
    acml_vol: str = Field(description="거래량")
    acml_tr_pbmn: str = Field(description="거래대금")
    flng_cls_code: str = Field(description="락 구분 코드")
    prtt_rate: str = Field(description="분할 비율")
    mod_yn: str = Field(description="변경 여부")
    prdy_vrss_sign: str = Field(description="전일 대비 부호")
    prdy_vrss: str = Field(description="전일 대비")
    revl_issu_reas: str = Field(description="재평가 사유 코드")


class DailyChartResponseBody(BaseModel):
    """일/주/월/년봉 API 응답 바디"""

    rt_cd: str = Field(description="성공 실패 여부 (0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output1: DailyChartOutput1 = Field(description="전체 정보")
    output2: list[DailyChartOutput2] = Field(description="개별 봉 데이터")


# ===== 분봉 조회 =====


class MinuteChartRequestHeader(BaseModel):
    """분봉 요청 헤더"""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "FHKST03010230"
    custtype: str | None = None


class MinuteChartRequestQueryParam(BaseModel):
    """분봉 요청 쿼리 파라미터"""

    FID_COND_MRKT_DIV_CODE: MarketCode  # 시장 분류 코드
    FID_INPUT_ISCD: str  # 종목코드
    FID_INPUT_HOUR_1: str  # 입력 시간1 (HHMMSS)
    FID_INPUT_DATE_1: str  # 입력 날짜1 (YYYYMMDD)
    FID_PW_DATA_INCU_YN: str = "N"  # 과거 데이터 포함 여부
    FID_FAKE_TICK_INCU_YN: str = ""  # 허봉 포함 여부


class MinuteChartOutput1(BaseModel):
    """분봉 output1 (전체 정보)"""

    prdy_vrss: str = Field(description="전일 대비")
    prdy_vrss_sign: str = Field(description="전일 대비 부호")
    prdy_ctrt: str = Field(description="전일 대비율")
    stck_prdy_clpr: str = Field(description="전일 종가")
    acml_vol: str = Field(description="누적 거래량")
    acml_tr_pbmn: str = Field(description="누적 거래대금")
    hts_kor_isnm: str = Field(description="한글 종목명")
    stck_prpr: str = Field(description="현재가")


class MinuteChartOutput2(BaseModel):
    """분봉 output2 (개별 분봉 데이터)"""

    stck_bsop_date: str = Field(description="영업 일자")
    stck_cntg_hour: str = Field(description="체결 시간")
    stck_prpr: str = Field(description="현재가")
    stck_oprc: str = Field(description="시가")
    stck_hgpr: str = Field(description="최고가")
    stck_lwpr: str = Field(description="최저가")
    cntg_vol: str = Field(description="체결 거래량")
    acml_tr_pbmn: str = Field(description="누적 거래대금")


class MinuteChartResponseBody(BaseModel):
    """분봉 API 응답 바디"""

    rt_cd: str = Field(description="성공 실패 여부 (0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output1: MinuteChartOutput1 = Field(description="전체 정보")
    output2: list[MinuteChartOutput2] = Field(description="개별 분봉 데이터")
