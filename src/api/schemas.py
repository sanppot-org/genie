"""API 스키마 정의"""
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.common.candle_client import CandleInterval
from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database import Ticker
from src.service.candle_service import CollectMode
from src.service.preferred_stock import common_code_of, is_preferred


class SellResponse(BaseModel):
    """매도 응답 모델"""

    success: bool
    message: str
    executed_volume: float | None = None
    remaining_volume: float | None = None


class TickerCreate(BaseModel):
    """Ticker 생성 요청"""

    ticker: str
    asset_type: AssetType
    data_source: DataSource

    def to_entity(self) -> Ticker:
        """Ticker 엔티티로 변환"""
        return Ticker(
            ticker=self.ticker,
            asset_type=self.asset_type,
            data_source=self.data_source.value,
        )


class TickerResponse(BaseModel):
    """Ticker 응답"""

    id: int
    ticker: str
    name: str
    asset_type: AssetType
    data_source: DataSource
    timezone: str | None = None
    is_preferred: bool = False
    common_ticker: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_ticker(cls, ticker: Ticker) -> "TickerResponse":
        """Ticker 엔티티에서 응답 생성"""
        # DataSource는 str Enum이므로 값으로 멤버 조회
        source = DataSource(ticker.data_source)  # type: ignore[call-arg]
        asset_type = AssetType(ticker.asset_type)
        is_pref = is_preferred(ticker.ticker, asset_type)
        common = common_code_of(ticker.ticker, asset_type)
        return cls(
            id=ticker.id,
            ticker=ticker.ticker,
            name=ticker.name,
            asset_type=ticker.asset_type,
            data_source=source,
            timezone=source.timezone,
            is_preferred=is_pref,
            common_ticker=common,
        )


class FundamentalPoint(BaseModel):
    """일자별 펀더멘털 단일 스냅샷."""

    date: date
    per: float | None = None
    pbr: float | None = None
    bps: float | None = None
    eps: float | None = None
    div: float | None = None
    dps: float | None = None

    model_config = ConfigDict(from_attributes=True)


class FundamentalSeriesResponse(BaseModel):
    """ticker별 펀더멘털 시계열."""

    ticker: str
    name: str
    points: list[FundamentalPoint]


class DividendPoint(BaseModel):
    """배당 지급 1건."""

    record_date: date
    kind: str  # "SETTLE" | "INTERIM"
    dps: float
    fiscal_year: int

    model_config = ConfigDict(from_attributes=True)


class DividendSeriesResponse(BaseModel):
    """ticker별 배당 지급 이력."""

    ticker: str
    name: str
    points: list[DividendPoint]


class IncomeStatementPoint(BaseModel):
    """결산기별 손익계산서 1건 (금액 단위: 억원)."""

    stac_yymm: str  # 결산년월 YYYYMM
    revenue: float | None = None           # 매출액
    cost_of_sales: float | None = None     # 매출원가
    gross_profit: float | None = None      # 매출총이익
    operating_profit: float | None = None  # 영업이익
    ordinary_profit: float | None = None   # 경상이익
    net_income: float | None = None        # 당기순이익
    eps: float | None = None               # 주당순이익 (결산말일 펀더멘털 스냅샷, 추정행은 컨센서스)
    per: float | None = None               # 주가수익률 (결산말일 펀더멘털 스냅샷, 추정행은 컨센서스)
    dps: float | None = None               # 주당배당금 (결산말일 펀더멘털 스냅샷, 추정행은 None)
    div: float | None = None               # 시가배당율(%) (결산말일 펀더멘털 스냅샷, 추정행은 None)
    price: float | None = None             # 주가 종가 (결산말일 일봉 스냅샷, 추정행은 None)
    is_estimate: bool = False              # True=컨센서스 추정(2026E 등), False=확정 실적


class IncomeStatementSeriesResponse(BaseModel):
    """ticker별 손익계산서 시계열."""

    ticker: str
    name: str
    period_type: str       # ANNUAL | QUARTER
    single_quarter: bool   # 분기 단일환산 적용 여부
    points: list[IncomeStatementPoint]


class SyncFinancialsResponse(BaseModel):
    """KIS 손익계산서 동기화 응답."""

    ticker_count: int
    skipped_current: int
    api_calls_attempted: int
    api_calls_failed: int
    rows_received: int
    rows_upserted: int
    chunks_committed: int
    chunks_failed: int


class GenieResponse[T](BaseModel):
    """공통 API 응답 모델"""

    data: T

    model_config = ConfigDict(from_attributes=True)


class CollectCandlesRequest(BaseModel):
    """1분봉 수집 요청"""

    ticker_id: int
    to: datetime | None = None
    start: datetime | None = None
    batch_size: int = 1000
    mode: CollectMode = CollectMode.INCREMENTAL


class CollectCandlesResponse(BaseModel):
    """1분봉 수집 응답"""

    total_saved: int
    ticker_id: int
    ticker: str
    mode: CollectMode


class QueryCandlesRequest(BaseModel):
    """캔들 조회 요청"""

    ticker_id: int
    interval: CandleInterval = CandleInterval.DAY
    count: int = 100
    end_time: datetime | None = None


class CandleData(BaseModel):
    """캔들 데이터"""

    timestamp: datetime
    local_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class QueryCandlesResponse(BaseModel):
    """캔들 조회 응답"""

    ticker_id: int
    ticker: str
    interval: CandleInterval
    count: int
    candles: list[CandleData]


class SyncTickersResponse(BaseModel):
    """pykrx 종목 동기화 응답"""

    inserted: int
    deactivated: int
    renamed: int
    reactivated: int
    unchanged: int


class SyncFundamentalsResponse(BaseModel):
    """pykrx 펀더멘털 동기화 응답"""

    date: date
    received: int
    upserted: int
    skipped_unmapped: int


class SyncDailyCandlesResponse(BaseModel):
    """pykrx KR 주식 일봉 동기화 응답"""

    date: date
    received: int
    upserted: int
    skipped_unmapped: int
    skipped_no_trade: int


class StockDailyCandlePoint(BaseModel):
    """일자별 KR 주식 일봉 단일 스냅샷."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_value: int | None = None

    model_config = ConfigDict(from_attributes=True)


class StockDailyCandleSeriesResponse(BaseModel):
    """ticker별 KR 주식 일봉 시계열."""

    ticker: str
    name: str
    points: list[StockDailyCandlePoint]


class AdjustedBackfillResponse(BaseModel):
    """수정주가 백필 결과."""

    ticker: str
    fetched: int
    updated: int
    existing: int = 0
    partial: bool = False
    from_date: date | None = None
    to_date: date | None = None


class ScreeningScoreBreakdown(BaseModel):
    """8개 지표별 점수 (PER 20 + PBR 5 + 배당 10 + 분기 5 + 연속 5 + 매입소각 7 + 소각비율 8 + 보유 5 = 65)."""

    per: int
    pbr: int
    dividend_yield: int
    quarterly_dividend: int
    consecutive_increase_years: int
    regular_buyback: int
    annual_cancel_ratio: int
    treasury_holding: int


class ScreeningRowResponse(BaseModel):
    """스크리닝 결과 1종목."""

    ticker: str
    name: str
    per: float | None = None
    pbr: float | None = None
    roe: float | None = None
    dividend_yield: float | None = None
    quarterly_dividend: bool
    consecutive_increase_years: int
    regular_buyback: bool
    annual_cancel_ratio: float | None = None
    treasury_ratio: float | None = None
    scores: ScreeningScoreBreakdown
    total_score: int


class ScreeningResponse(BaseModel):
    """KR_STOCK 점수 스크리닝 응답."""

    target_date: date | None
    total: int
    limit: int
    offset: int
    max_score: int
    rows: list[ScreeningRowResponse]


class FilterPredicate(BaseModel):
    """시계열 연산(count/streak)의 연도별 판정 술어."""

    cmp: Literal["lt", "lte", "gt", "gte", "eq"]
    value: float


class FilterCondition(BaseModel):
    """단일 조건. op별 필수 필드는 서버(validate_condition)가 최종 검증."""

    metric: str
    op: Literal["cmp", "count", "cagr", "streak", "avg"]
    cmp: Literal["lt", "lte", "gt", "gte", "eq"] | None = None
    value: float | None = None
    window: int | None = Field(default=None, ge=1, le=20)
    min_count: int | None = Field(default=None, ge=1)
    predicate: FilterPredicate | None = None


class FilterScreeningRequest(BaseModel):
    """조건 필터 스크리닝 요청 (조건은 AND)."""

    conditions: list[FilterCondition] = Field(min_length=1, max_length=20)
    sort_by: str = "total_score"
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class FilterScreeningRowResponse(BaseModel):
    """조건 필터 결과 1종목. metrics는 참조된 지표만 동적으로 포함."""

    ticker: str
    name: str
    total_score: int | None = None
    metrics: dict[str, Any]


class FilterScreeningResponse(BaseModel):
    """조건 필터 스크리닝 응답."""

    total: int
    limit: int
    offset: int
    rows: list[FilterScreeningRowResponse]


# ---------------------------------------------------------------------------
# Lab (백테스트 + US 데이터 관리) 스키마
# ---------------------------------------------------------------------------

class StrategyInfo(BaseModel):
    """전략 레지스트리 1건."""

    name: str
    timeframe: str
    description: str
    default_params: dict[str, object] = Field(default_factory=dict)


class BacktestRunRequest(BaseModel):
    """백테스트 실행 요청."""

    ticker: str
    strategies: list[str] = Field(min_length=1, max_length=20)
    start: str | None = None          # YYYYMMDD
    end: str | None = None            # YYYYMMDD
    initial_cash: float = Field(default=10_000_000.0, gt=0)
    commission: float = Field(default=0.0005, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    asset: Literal["stock", "crypto"] = "stock"
    param_overrides: dict[str, Any] | None = None


class BacktestEquityPoint(BaseModel):
    """자산곡선 1점 (일 단위). return_pct는 초기자본 대비, drawdown_pct는 고점 대비(≤ 0)."""

    date: date
    return_pct: float
    drawdown_pct: float


class BacktestRunItem(BaseModel):
    """전략별 백테스트 결과."""

    strategy_name: str
    timeframe: str
    initial_cash: float
    final_value: float
    total_return_pct: float
    cagr_pct: float | None
    max_drawdown_pct: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None = None  # 소르티노 비율 (연율화, MAR=0), 산출 불가 시 None
    total_trades: int
    win_rate_pct: float | None
    period_days: int | None
    start_date: date | None = None  # 실제 사용된 데이터 첫 봉 날짜
    end_date: date | None = None    # 실제 사용된 데이터 마지막 봉 날짜
    bust: bool
    equity_curve: list[BacktestEquityPoint] | None = None  # 일별 자산곡선, 산출 불가 시 None


class BacktestRunResponse(BaseModel):
    """백테스트 실행 전체 응답."""

    results: list[BacktestRunItem]
    skipped: list[str]        # 캔들 데이터 없어 제외된 전략명
    failed: list[str]         # 실행 예외로 실패한 전략명
    mixed_timeframes: bool    # 결과 전략들의 타임프레임이 혼합되어 있으면 True
    benchmark: list[BacktestEquityPoint] | None = None  # Buy & Hold 벤치마크 (종가 기반)


class CorrelationRequest(BaseModel):
    """멀티 티커 상관관계 분석 요청."""

    tickers: list[str] = Field(min_length=2, max_length=20)
    start: str | None = None              # YYYYMMDD
    end: str | None = None                # YYYYMMDD
    asset: Literal["stock"] = "stock"     # 1차 릴리스는 일봉 stock만
    method: Literal["pearson", "spearman"] = "pearson"
    return_type: Literal["returns", "price"] = "returns"


class CorrelationResponse(BaseModel):
    """상관관계 분석 응답. matrix[i][j] = tickers[i]·tickers[j] 상관계수(대각 1.0, 계산불가 null)."""

    tickers: list[str]                    # 행/열 순서 (정렬 후 최종 포함 티커)
    matrix: list[list[float | None]]      # N×N
    observations: int                     # 정렬·dropna 후 공통 관측 수
    period_start: date | None
    period_end: date | None
    method: str
    return_type: str
    dropped: list[str]                    # 미등록·무데이터로 제외된 티커
    warnings: list[str]


class UsRegisterRequest(BaseModel):
    """미국 주식 종목 등록 요청."""

    symbols: list[str] = Field(min_length=1, max_length=50)


class UsRegisterResult(BaseModel):
    """미국 주식 종목 등록 결과."""

    registered: int
    updated: int
    skipped_unknown: int
    skipped: list[str]


class UsBackfillRequest(BaseModel):
    """미국 주식 일봉 백필 요청."""

    symbols: list[str] = Field(min_length=1, max_length=50)
    start: str | None = None          # YYYYMMDD; 미지정 시 서비스 기본값(1990-01-01)


class UsBackfillResult(BaseModel):
    """미국 주식 일봉 백필 결과."""

    ticker_count: int
    attempted: int
    failed: int
    tickers_upserted: int
    rows_upserted: int
    failed_tickers: list[str]


class UsTickerInfo(BaseModel):
    """미국 티커 1건 + 데이터 보유 현황."""

    ticker: str
    name: str | None
    asset_type: str
    exchange: str | None
    candle_count: int
    first_date: date | None
    last_date: date | None
