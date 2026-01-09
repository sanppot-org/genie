"""SQLAlchemy models for TimescaleDB."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class CandleBase(Base):
    """캔들 데이터 공통 베이스 모델 (추상 클래스)

    Attributes:
        id: 자동 증가 ID (primary key 아님)
        ticker: 티커 (예: KRW-BTC)
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

    id: Mapped[int | None] = mapped_column(Integer, autoincrement=True, nullable=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)


class CandleMinute1(CandleBase):
    """1분봉 캔들 데이터 모델

    Attributes:
        timestamp: 캔들 시각 (UTC, timezone-aware)
        localtime: 캔들 시각 (KST, naive datetime)
    """

    __tablename__ = "candle_minute_1"

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    localtime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    __table_args__ = (
        PrimaryKeyConstraint("localtime", "ticker"),
        UniqueConstraint("localtime", "ticker", name="uix_minute1_localtime_ticker"),
        Index("idx_minute1_ticker_localtime", "ticker", "localtime"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleMinute1(ticker={self.ticker}, timestamp={self.timestamp}, close={self.close})>"


class CandleDaily(CandleBase):
    """일봉 캔들 데이터 모델

    Attributes:
        date: 캔들 날짜 (timezone 없음)
    """

    __tablename__ = "candle_daily"

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        PrimaryKeyConstraint("date", "ticker"),
        UniqueConstraint("date", "ticker", name="uix_daily_date_ticker"),
        Index("idx_daily_ticker_date", "ticker", "date"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleDaily(ticker={self.ticker}, date={self.date}, close={self.close})>"


class Exchange(Base):
    """거래소 마스터 테이블

    Attributes:
        id: 자동 증가 ID (primary key)
        name: 거래소 이름 (예: Upbit, Binance)
    """

    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<Exchange(name={self.name})>"


class Ticker(Base):
    """티커 마스터 테이블

    자산(암호화폐, 주식, ETF 등)의 티커 정보를 관리합니다.

    Attributes:
        id: 자동 증가 PK
        ticker: 티커 코드 (예: KRW-BTC, AAPL, 005930)
        asset_type: 자산 유형 (CRYPTO, STOCK, ETF)
    """

    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<Ticker(ticker={self.ticker}, asset_type={self.asset_type})>"
