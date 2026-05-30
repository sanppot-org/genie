"""API 스키마 정의"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from src.common.candle_client import CandleInterval
from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database import Ticker
from src.service.candle_service import CollectMode


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

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_ticker(cls, ticker: Ticker) -> "TickerResponse":
        """Ticker 엔티티에서 응답 생성"""
        # DataSource는 str Enum이므로 값으로 멤버 조회
        source = DataSource(ticker.data_source)  # type: ignore[call-arg]
        return cls(
            id=ticker.id,
            ticker=ticker.ticker,
            name=ticker.name,
            asset_type=ticker.asset_type,
            data_source=source,
            timezone=source.timezone,
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
    eps: float | None = None               # 주당순이익 (결산말일 펀더멘털 스냅샷)
    per: float | None = None               # 주가수익률 (결산말일 펀더멘털 스냅샷)
    price: float | None = None             # 주가 종가 (결산말일 일봉 스냅샷)


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
