"""SQLAlchemy models for TimescaleDB."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Identity, Integer, PrimaryKeyConstraint, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.constants import AssetType, TimeZone


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
        - CandleMinute1: timestamp (UTC), localtime (KST)
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
        timestamp: 캔들 시각 (UTC, timezone-aware)
        local_time: 캔들 시각 (KST, naive datetime)
    """

    __tablename__ = "candle_minute_1"

    id: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    local_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    __table_args__ = (
        PrimaryKeyConstraint("local_time", "ticker_id"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleMinute1(ticker_id={self.ticker_id}, timestamp={self.timestamp}, close={self.close})>"


class CandleHour1(CandleBase):
    """1시간봉 캔들 데이터 모델 (MATERIALIZED VIEW - 읽기 전용)

    Attributes:
        local_time: 캔들 시각 (KST, naive datetime)
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


class Exchange(Base, TimestampMixin):
    """거래소 마스터 테이블

    Attributes:
        id: 자동 증가 ID (primary key)
        name: 거래소 이름 (예: Upbit, Binance)
        timezone: 거래소 시간대 (예: Asia/Seoul, UTC)
    """

    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    timezone: Mapped[TimeZone] = mapped_column(String(50), nullable=False)

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<Exchange(name={self.name}, timezone={self.timezone})>"


class Ticker(Base, TimestampMixin):
    """티커 마스터 테이블

    자산(암호화폐, 주식, ETF 등)의 티커 정보를 관리합니다.

    Attributes:
        id: 자동 증가 PK
        ticker: 티커 코드 (예: KRW-BTC, AAPL, 005930)
        asset_type: 자산 유형 (CRYPTO, STOCK, ETF)
        exchange_id: 거래소 FK
        exchange: 거래소 관계
    """

    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    asset_type: Mapped[AssetType] = mapped_column(String(20), nullable=False, index=True)
    exchange_id: Mapped[int] = mapped_column(Integer, ForeignKey("exchanges.id"), nullable=False, index=True)

    exchange: Mapped["Exchange"] = relationship("Exchange", lazy="joined")

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<Ticker(ticker={self.ticker}, asset_type={self.asset_type}, exchange_id={self.exchange_id})>"
