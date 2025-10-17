"""주식 현재가 시세 조회 모델"""

from pydantic import BaseModel, Field

from src.hantu.model.domestic.market_code import MarketCode


class RequestHeader(BaseModel):
    """요청 헤더"""

    content_type: str = Field(default="application/json; charset=utf-8", alias="Content-Type")
    authorization: str
    appkey: str
    appsecret: str
    tr_id: str = "FHKST01010100"  # 실전/모의 동일
    custtype: str | None = None


class RequestQueryParam(BaseModel):
    """요청 쿼리 파라미터"""

    FID_COND_MRKT_DIV_CODE: MarketCode  # 조건 시장 분류 코드
    FID_INPUT_ISCD: str  # 종목코드


class StockPriceOutput(BaseModel):
    """주식 현재가 시세 응답 output

    한국투자증권 주식현재가 시세 API의 전체 응답 필드 정의.
    총 79개 필드 포함.
    """

    # ===== 기본 시세 정보 =====
    stck_prpr: str = Field(description="주식 현재가")
    stck_oprc: str = Field(description="시가")
    stck_hgpr: str = Field(description="고가")
    stck_lwpr: str = Field(description="저가")
    stck_mxpr: str = Field(description="상한가")
    stck_llam: str = Field(description="하한가")
    stck_sdpr: str = Field(description="기준가")
    stck_prdy_clpr: str | None = Field(default=None, description="전일 종가")

    # ===== 전일 대비 =====
    prdy_vrss: str = Field(description="전일 대비")
    prdy_vrss_sign: str = Field(description="전일 대비 부호")
    prdy_ctrt: str = Field(description="전일 대비율")

    # ===== 거래 정보 =====
    acml_vol: str = Field(description="누적 거래량")
    acml_tr_pbmn: str = Field(description="누적 거래대금")
    prdy_vrss_vol_rate: str | None = Field(default=None, description="전일 대비 거래량 비율")
    vol_tnrt: str | None = Field(default=None, description="거래량 회전율")

    # ===== 가격 및 호가 정보 =====
    wghn_avrg_stck_prc: str | None = Field(default=None, description="가중 평균 주식 가격")
    rstc_wdth_prc: str | None = Field(default=None, description="제한 폭 가격")
    stck_fcam: str | None = Field(default=None, description="주식 액면가")
    stck_sspr: str | None = Field(default=None, description="주식 대용가")
    aspr_unit: str | None = Field(default=None, description="호가단위")
    hts_deal_qty_unit_val: str | None = Field(default=None, description="HTS 매매 수량 단위 값")
    dmrs_val: str | None = Field(default=None, description="디저항 값")
    dmsp_val: str | None = Field(default=None, description="디지지 값")

    # ===== 재무 정보 =====
    per: str | None = Field(default=None, description="PER")
    pbr: str | None = Field(default=None, description="PBR")
    eps: str | None = Field(default=None, description="EPS")
    bps: str | None = Field(default=None, description="BPS")
    cpfn: str | None = Field(default=None, description="자본금")
    lstn_stcn: str | None = Field(default=None, description="상장 주수")
    hts_avls: str | None = Field(default=None, description="HTS 시가총액")
    stac_month: str | None = Field(default=None, description="결산 월")
    fcam_cnnm: str | None = Field(default=None, description="액면가 통화명")
    cpfn_cnnm: str | None = Field(default=None, description="자본금 통화명")

    # ===== 외국인/프로그램 매매 =====
    hts_frgn_ehrt: str | None = Field(default=None, description="HTS 외국인 소진율")
    frgn_ntby_qty: str | None = Field(default=None, description="외국인 순매수 수량")
    frgn_hldn_qty: str | None = Field(default=None, description="외국인 보유 수량")
    pgtr_ntby_qty: str | None = Field(default=None, description="프로그램매매 순매수 수량")

    # ===== 피벗 포인트 =====
    pvt_scnd_dmrs_prc: str | None = Field(default=None, description="피벗 2차 디저항 가격")
    pvt_frst_dmrs_prc: str | None = Field(default=None, description="피벗 1차 디저항 가격")
    pvt_pont_val: str | None = Field(default=None, description="피벗 포인트 값")
    pvt_frst_dmsp_prc: str | None = Field(default=None, description="피벗 1차 디지지 가격")
    pvt_scnd_dmsp_prc: str | None = Field(default=None, description="피벗 2차 디지지 가격")

    # ===== 52주/250일/연중 최고가/최저가 =====
    # 250일
    d250_hgpr: str | None = Field(default=None, description="250일 최고가")
    d250_hgpr_date: str | None = Field(default=None, description="250일 최고가 일자")
    d250_hgpr_vrss_prpr_rate: str | None = Field(default=None, description="250일 최고가 대비 현재가 비율")
    d250_lwpr: str | None = Field(default=None, description="250일 최저가")
    d250_lwpr_date: str | None = Field(default=None, description="250일 최저가 일자")
    d250_lwpr_vrss_prpr_rate: str | None = Field(default=None, description="250일 최저가 대비 현재가 비율")

    # 연중
    stck_dryy_hgpr: str | None = Field(default=None, description="주식 연중 최고가")
    dryy_hgpr_vrss_prpr_rate: str | None = Field(default=None, description="연중 최고가 대비 현재가 비율")
    dryy_hgpr_date: str | None = Field(default=None, description="연중 최고가 일자")
    stck_dryy_lwpr: str | None = Field(default=None, description="주식 연중 최저가")
    dryy_lwpr_vrss_prpr_rate: str | None = Field(default=None, description="연중 최저가 대비 현재가 비율")
    dryy_lwpr_date: str | None = Field(default=None, description="연중 최저가 일자")

    # 52주
    w52_hgpr: str | None = Field(default=None, description="52주일 최고가")
    w52_hgpr_vrss_prpr_ctrt: str | None = Field(default=None, description="52주일 최고가 대비 현재가 대비")
    w52_hgpr_date: str | None = Field(default=None, description="52주일 최고가 일자")
    w52_lwpr: str | None = Field(default=None, description="52주일 최저가")
    w52_lwpr_vrss_prpr_ctrt: str | None = Field(default=None, description="52주일 최저가 대비 현재가 대비")
    w52_lwpr_date: str | None = Field(default=None, description="52주일 최저가 일자")

    # ===== 종목 상태 및 시장 정보 =====
    hts_kor_isnm: str | None = Field(default=None, description="HTS 한글 종목명")
    iscd_stat_cls_code: str | None = Field(default=None, description="종목 상태 구분 코드")
    marg_rate: str | None = Field(default=None, description="증거금 비율")
    rprs_mrkt_kor_name: str | None = Field(default=None, description="대표 시장 한글 명")
    new_hgpr_lwpr_cls_code: str | None = Field(default=None, description="신 고가 저가 구분 코드")
    bstp_kor_isnm: str | None = Field(default=None, description="업종 한글 종목명")
    temp_stop_yn: str | None = Field(default=None, description="임시 정지 여부")
    oprc_rang_cont_yn: str | None = Field(default=None, description="시가 범위 연장 여부")
    clpr_rang_cont_yn: str | None = Field(default=None, description="종가 범위 연장 여부")
    crdt_able_yn: str | None = Field(default=None, description="신용 가능 여부")
    grmn_rate_cls_code: str | None = Field(default=None, description="보증금 비율 구분 코드")
    elw_pblc_yn: str | None = Field(default=None, description="ELW 발행 여부")

    # ===== 기타 메타 정보 =====
    whol_loan_rmnd_rate: str | None = Field(default=None, description="전체 융자 잔고 비율")
    ssts_yn: str | None = Field(default=None, description="공매도가능여부")
    stck_shrn_iscd: str | None = Field(default=None, description="주식 단축 종목코드")
    apprch_rate: str | None = Field(default=None, description="접근도")
    vi_cls_code: str | None = Field(default=None, description="VI적용구분코드")
    ovtm_vi_cls_code: str | None = Field(default=None, description="시간외단일가VI적용구분코드")
    last_ssts_cntg_qty: str | None = Field(default=None, description="최종 공매도 체결 수량")
    invt_caful_yn: str | None = Field(default=None, description="투자유의여부")
    mrkt_warn_cls_code: str | None = Field(default=None, description="시장경고코드")
    short_over_yn: str | None = Field(default=None, description="단기과열여부")
    sltr_yn: str | None = Field(default=None, description="정리매매여부")
    mang_issu_cls_code: str | None = Field(default=None, description="관리종목여부")


class ResponseBody(BaseModel):
    """API 응답 바디"""

    rt_cd: str = Field(description="성공 실패 여부 (0:성공, 0 이외:실패)")
    msg_cd: str = Field(description="응답코드")
    msg1: str = Field(description="응답메시지")
    output: StockPriceOutput = Field(description="응답 상세")
