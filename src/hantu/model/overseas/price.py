"""해외주식 시세 조회 관련 모델"""

from pydantic import BaseModel, Field


class OverseasCurrentPriceData(BaseModel):
    """해외주식 현재체결가 데이터"""

    rsym: str = Field(..., description="실시간조회종목코드")
    zdiv: str = Field(..., description="소수점자리수")
    base: str = Field(..., description="전일종가")
    pvol: str = Field(..., description="전일거래량")
    last: str = Field(..., description="현재가")
    sign: str = Field(..., description="대비기호")
    diff: str = Field(..., description="대비")
    rate: str = Field(..., description="등락율")
    tvol: str = Field(..., description="거래량")
    tamt: str = Field(..., description="거래대금")
    ordy: str = Field(..., description="매수가능여부")


class OverseasCurrentPriceResponse(BaseModel):
    """해외주식 현재체결가 응답"""

    output: OverseasCurrentPriceData = Field(..., description="응답 데이터")


class OverseasDailyCandleData(BaseModel):
    """해외주식 종목/지수/환율 일/주/월/년 캔들 데이터

    KIS API inquire-daily-chartprice 응답 필드:
    - stck_bsop_date: 영업 일자
    - ovrs_nmix_prpr: 현재가(종가)
    - ovrs_nmix_oprc: 시가
    - ovrs_nmix_hgpr: 고가
    - ovrs_nmix_lwpr: 저가
    - acml_vol: 누적 거래량
    - mod_yn: 변경 여부
    """

    stck_bsop_date: str = Field(..., description="영업 일자 (YYYYMMDD)")
    ovrs_nmix_prpr: str = Field(..., description="현재가(종가)")
    ovrs_nmix_oprc: str = Field(..., description="시가")
    ovrs_nmix_hgpr: str = Field(..., description="고가")
    ovrs_nmix_lwpr: str = Field(..., description="저가")
    acml_vol: str = Field(..., description="누적 거래량")
    mod_yn: str = Field(default="N", description="변경 여부")


class OverseasDailyCandleResponse(BaseModel):
    """해외주식 일/주/월/년 캔들 응답

    KIS API 응답 구조:
    - output1: 요약 정보 (dict) 또는 캔들 데이터 (list)
    - output2: 캔들 데이터 (list) 또는 추가 정보 (dict)

    일반적으로 output2에 캔들 데이터가 리스트로 반환됩니다.
    """

    output1: dict | list[OverseasDailyCandleData] = Field(default_factory=dict, description="요약 정보 또는 캔들 데이터")
    output2: list[OverseasDailyCandleData] | dict = Field(default_factory=list, description="캔들 데이터 또는 추가 정보")

    @property
    def candles(self) -> list[OverseasDailyCandleData]:
        """캔들 데이터 리스트 반환"""
        # output2가 캔들 리스트인 경우 (일반적)
        if isinstance(self.output2, list):
            return self.output2
        # output1이 캔들 리스트인 경우 (대체)
        if isinstance(self.output1, list):
            return self.output1
        return []


class OverseasOrderbookItem(BaseModel):
    """호가 항목"""

    askp: str = Field(..., description="매도호가")
    bidp: str = Field(..., description="매수호가")
    askp_rsqn: str = Field(..., description="매도호가잔량")
    bidp_rsqn: str = Field(..., description="매수호가잔량")


class OverseasOrderbookData(BaseModel):
    """호가 정보"""

    rsym: str = Field(..., description="실시간조회종목코드")
    zdiv: str = Field(..., description="소수점자리수")
    base: str = Field(..., description="기준가")


class OverseasOrderbookResponse(BaseModel):
    """호가 정보 응답"""

    output1: OverseasOrderbookData = Field(..., description="호가 기본 정보")
    output2: list[OverseasOrderbookItem] = Field(default_factory=list, description="호가 목록")


class OverseasMinuteCandleMetadata(BaseModel):
    """해외주식 분봉 메타데이터 (output1)"""

    rsym: str = Field(..., description="실시간조회종목코드")
    zdiv: str = Field(..., description="소수점자리수")
    stim: str = Field(..., description="시작시간")
    etim: str = Field(..., description="종료시간")
    sktm: str = Field(..., description="한국시작시간")
    ektm: str = Field(..., description="한국종료시간")
    next: str = Field(..., description="다음조회키")
    more: str = Field(..., description="연속조회여부")
    nrec: str = Field(..., description="조회건수")


class OverseasMinuteCandleData(BaseModel):
    """해외주식 분봉 데이터 (output2)"""

    tymd: str = Field(..., description="거래소 현지 날짜 (YYYYMMDD)")
    xymd: str = Field(..., description="한국 기준 날짜 (YYYYMMDD)")
    xhms: str = Field(..., description="한국 기준 시간 (HHMMSS)")
    kymd: str = Field(..., description="한국 날짜 (YYYYMMDD)")
    khms: str = Field(..., description="한국 시간 (HHMMSS)")
    open: str = Field(..., description="시가")
    high: str = Field(..., description="고가")
    low: str = Field(..., description="저가")
    last: str = Field(..., description="종가")
    evol: str = Field(..., description="거래량")
    eamt: str = Field(..., description="거래대금")


class OverseasMinuteCandleResponse(BaseModel):
    """해외주식 분봉 응답"""

    output1: OverseasMinuteCandleMetadata = Field(..., description="메타데이터")
    output2: list[OverseasMinuteCandleData] = Field(default_factory=list, description="분봉 데이터 목록")
