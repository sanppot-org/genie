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
    """해외주식 일/주/월/년 캔들 데이터"""

    xymd: str = Field(..., description="일자")
    clos: str = Field(..., description="종가")
    sign: str = Field(..., description="전일대비부호")
    diff: str = Field(..., description="전일대비")
    rate: str = Field(..., description="등락률")
    open: str = Field(..., description="시가")
    high: str = Field(..., description="고가")
    low: str = Field(..., description="저가")
    tvol: str = Field(..., description="거래량")
    tamt: str = Field(..., description="거래대금")


class OverseasDailyCandleResponse(BaseModel):
    """해외주식 일/주/월/년 캔들 응답"""

    output1: list[OverseasDailyCandleData] = Field(default_factory=list, description="캔들 데이터 목록")
    output2: dict | None = Field(None, description="추가 정보")


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
