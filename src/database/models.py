"""SQLAlchemy models for TimescaleDB."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    func,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.common.data_adapter import DataSource
from src.constants import AssetType


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """생성/수정 일시 공통 믹스인"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CandleBase(Base):
    """캔들 데이터 공통 베이스 모델 (추상 클래스)

    Attributes:
        id: 자동 증가 ID (primary key 아님)
        ticker_id: 티커 (예: KRW-BTC)
        open: 시가
        high: 고가
        low: 저가
        close: 종가
        volume: 거래량

    Note:
        시간 필드는 각 서브클래스에서 정의합니다.
        - CandleMinute1: timestamp (UTC), local_time (거래소 현지 시간, naive)
        - CandleDaily: date (날짜만)
    """

    __abstract__ = True  # 추상 클래스로 설정 (테이블 생성 안 함)

    ticker_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)


class CandleMinute1(CandleBase, TimestampMixin):
    """1분봉 캔들 데이터 모델

    Attributes:
        utc_time: 캔들 시각 (UTC, timezone-aware)
        local_time: 캔들 시각 (거래소 현지 시간, naive)
    """

    __tablename__ = "candle_minute_1"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), nullable=True)
    utc_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    local_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    __table_args__ = (
        PrimaryKeyConstraint("local_time", "ticker_id"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleMinute1(ticker_id={self.ticker_id}, utc_time={self.utc_time}, close={self.close})>"


class CandleHour1(CandleBase):
    """1시간봉 캔들 데이터 모델 (MATERIALIZED VIEW - 읽기 전용)

    Attributes:
        local_time: 캔들 시각 (거래소 현지 시간, naive)
    """

    __tablename__ = "candle_hour_1"

    local_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("local_time", "ticker_id"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleHour1(ticker_id={self.ticker_id}, kst_time={self.local_time}, close={self.close})>"


class CandleDaily(CandleBase):
    """일봉 캔들 데이터 모델 (MATERIALIZED VIEW - 읽기 전용)

    Attributes:
        date: 캔들 날짜 (timezone 없음)
    """

    __tablename__ = "candle_daily"

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        PrimaryKeyConstraint("date", "ticker_id"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleDaily(ticker_id={self.ticker_id}, date={self.date}, close={self.close})>"


def _default_name_from_ticker(context: object) -> str:
    """`name` 미지정 시 `ticker` 값을 그대로 사용."""
    name: str = context.get_current_parameters()["ticker"]  # type: ignore[attr-defined]
    return name


class Ticker(Base, TimestampMixin):
    """티커 마스터 테이블

    자산(암호화폐, 주식, ETF 등)의 티커 정보를 관리합니다.

    Attributes:
        id: 자동 증가 PK
        ticker: 티커 코드 (예: KRW-BTC, AAPL, 005930)
        asset_type: 자산 유형 (CRYPTO, STOCK, ETF)
        data_source: 데이터 소스 (UPBIT, BINANCE, HANTU)
    """

    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default=_default_name_from_ticker)
    asset_type: Mapped[AssetType] = mapped_column(String(20), nullable=False, index=True)
    data_source: Mapped[DataSource] = mapped_column(Enum(DataSource, native_enum=False), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    industry_code: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<Ticker(ticker={self.ticker}, asset_type={self.asset_type}, data_source={self.data_source})>"


class StockFundamental(Base, TimestampMixin):
    """일자별 종목 펀더멘털 (pykrx get_market_fundamental).

    KR_STOCK 대상. 동일 (date, ticker_id) 재호출 시 UPSERT.
    financial metric은 pykrx 빈 셀/적자 종목 대응을 위해 nullable.
    """

    __tablename__ = "stock_fundamentals"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), nullable=True)
    ticker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickers.id", name="fk_stock_fundamentals_ticker_id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, comment="펀더멘털 기준 영업일")
    per: Mapped[float | None] = mapped_column(Float, nullable=True, comment="주가수익률 = 주가 / EPS, 적자면 None")
    eps: Mapped[float | None] = mapped_column(Float, nullable=True, comment="주당순이익 (Earnings Per Share)")
    bps: Mapped[float | None] = mapped_column(Float, nullable=True, comment="주당순자산가치 (Book-value Per Share)")
    pbr: Mapped[float | None] = mapped_column(Float, nullable=True, comment="주가순자산배수 = 주가 / BPS")
    div: Mapped[float | None] = mapped_column(Float, nullable=True, comment="배당수익률(%) = DPS / 주가")
    dps: Mapped[float | None] = mapped_column(Float, nullable=True, comment="주당배당금 (Dividend Per Share)")

    __table_args__ = (
        PrimaryKeyConstraint("date", "ticker_id"),
        Index("ix_stock_fundamentals_ticker_id_date", "ticker_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<StockFundamental(ticker_id={self.ticker_id}, date={self.date}, per={self.per})>"


class StockDividend(Base, TimestampMixin):
    """KIS `ksdinfo_dividend` 기반 배당 이력.

    KR_STOCK 대상. 분기 배당 실시 여부 / 배당 연속 인상 연수 등 점수표 지표 산출용.
    동일 (ticker_id, record_date, kind) 재호출 시 UPSERT.
    """

    __tablename__ = "stock_dividends"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), nullable=True)
    ticker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickers.id", name="fk_stock_dividends_ticker_id"), nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False, comment="배당 기준일")
    pay_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="배당 지급일")
    dps: Mapped[float] = mapped_column(Float, nullable=False, comment="주당 배당금 (원, 단건)")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, comment="SETTLE: 결산, INTERIM: 중간/분기")
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, comment="회계연도 (record_date 기준)")

    __table_args__ = (
        PrimaryKeyConstraint("ticker_id", "record_date", "kind"),
        Index("ix_stock_dividends_ticker_id_record_date", "ticker_id", "record_date"),
    )

    def __repr__(self) -> str:
        return f"<StockDividend(ticker_id={self.ticker_id}, record_date={self.record_date}, kind={self.kind}, dps={self.dps})>"


class StockTreasuryStock(Base, TimestampMixin):
    """DART `stockTotqySttus`(주식의 총수 현황) 기반 자사주 보유 비율 시계열.

    KR_STOCK 대상. 자사주 보유 비율 점수 산출용.
    정기보고서(사업/반기/Q1/Q3) 기준이라 결산일별 1 row.
    동일 (ticker_id, stlm_dt) 재호출 시 UPSERT(가장 최근 보고서로 덮어쓰기).
    """

    __tablename__ = "stock_treasury_stocks"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), nullable=True)
    ticker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickers.id", name="fk_stock_treasury_stocks_ticker_id"), nullable=False
    )
    stlm_dt: Mapped[date] = mapped_column(Date, nullable=False, comment="결산일")
    reprt_code: Mapped[str] = mapped_column(String(5), nullable=False, comment="11011 사업/11012 반기/11013 Q1/11014 Q3")
    issued_shares: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="발행주식 총수 (보통주+우선주 합계)")
    treasury_shares: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="자기주식 수 (보통주+우선주 합계)")
    treasury_ratio: Mapped[float] = mapped_column(Float, nullable=False, comment="자사주 보유 비율(%) = treasury_shares / issued_shares * 100")
    rcept_no: Mapped[str | None] = mapped_column(String(14), nullable=True, comment="DART 접수번호")

    __table_args__ = (
        PrimaryKeyConstraint("ticker_id", "stlm_dt"),
        Index("ix_stock_treasury_stocks_ticker_id_stlm_dt", "ticker_id", "stlm_dt"),
    )

    def __repr__(self) -> str:
        return f"<StockTreasuryStock(ticker_id={self.ticker_id}, stlm_dt={self.stlm_dt}, ratio={self.treasury_ratio:.2f}%)>"


class StockBuybackEvent(Base, TimestampMixin):
    """DART 자기주식 취득·처분 결정 공시 이벤트.

    KR_STOCK 대상. 점수표 "정기적 자사주 매입·소각 (최소 연 1회 이상)" 판정용.
    PK는 (ticker_id, rcept_no) — DART 접수번호가 종목별 유일하므로 동일 공시 재호출은 UPSERT.
    """

    __tablename__ = "stock_buyback_events"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), nullable=True)
    ticker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickers.id", name="fk_stock_buyback_events_ticker_id"), nullable=False
    )
    rcept_no: Mapped[str] = mapped_column(String(14), nullable=False, comment="DART 접수번호")
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="ACQUISITION 취득결정 / DISPOSAL 처분결정")
    resolution_date: Mapped[date] = mapped_column(Date, nullable=False, comment="이사회 결의일 (aq_dd / dp_dd)")
    planned_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="예정 보통주 수량")
    planned_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="예정 보통주 금액(원)")
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True, comment="취득/처분 예정 시작일")
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True, comment="취득/처분 예정 종료일")
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="aq_pp / dp_pp 취득·처분 목적(자유 텍스트)")

    __table_args__ = (
        PrimaryKeyConstraint("ticker_id", "rcept_no"),
        Index("ix_stock_buyback_events_ticker_id_resolution_date", "ticker_id", "resolution_date"),
    )

    def __repr__(self) -> str:
        return f"<StockBuybackEvent(ticker_id={self.ticker_id}, type={self.event_type}, resolution_date={self.resolution_date})>"


class StockDailyCandle(Base, TimestampMixin):
    """KR 주식 일자별 OHLCV (pykrx get_market_ohlcv).

    KR_STOCK 대상. 동일 (date, ticker_id) 재호출 시 UPSERT.
    기존 candle_daily(MATERIALIZED VIEW)는 candle_minute_1 집계용이라 직접 INSERT 불가 → 별도 테이블.
    """

    __tablename__ = "stock_daily_candles"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), nullable=True)
    ticker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickers.id", name="fk_stock_daily_candles_ticker_id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, comment="거래 영업일")
    open: Mapped[float] = mapped_column(Float, nullable=False, comment="시가")
    high: Mapped[float] = mapped_column(Float, nullable=False, comment="고가")
    low: Mapped[float] = mapped_column(Float, nullable=False, comment="저가")
    close: Mapped[float] = mapped_column(Float, nullable=False, comment="종가")
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="거래량(주)")
    trade_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="거래대금(원)")

    __table_args__ = (
        PrimaryKeyConstraint("date", "ticker_id"),
        Index("ix_stock_daily_candles_ticker_id_date", "ticker_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<StockDailyCandle(ticker_id={self.ticker_id}, date={self.date}, close={self.close})>"
