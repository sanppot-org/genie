"""SQLAlchemy models for TimescaleDB."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class CandleBase(Base):
    """캔들 데이터 공통 베이스 모델 (추상 클래스)

    Attributes:
        id: 기본 키
        timestamp: 캔들 시각 (UTC)
        ticker: 티커 (예: KRW-BTC)
        open: 시가
        high: 고가
        low: 저가
        close: 종가
        volume: 거래량
    """

    __abstract__ = True  # 추상 클래스로 설정 (테이블 생성 안 함)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)


class CandleMinute1(CandleBase):
    """1분봉 캔들 데이터 모델"""

    __tablename__ = "candle_minute_1"

    __table_args__ = (
        UniqueConstraint("timestamp", "ticker", name="uix_minute1_timestamp_ticker"),
        Index("idx_minute1_ticker_timestamp", "ticker", "timestamp"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleMinute1(ticker={self.ticker}, timestamp={self.timestamp}, close={self.close})>"


class CandleDaily(CandleBase):
    """일봉 캔들 데이터 모델"""

    __tablename__ = "candle_daily"

    __table_args__ = (
        UniqueConstraint("timestamp", "ticker", name="uix_daily_timestamp_ticker"),
        Index("idx_daily_ticker_timestamp", "ticker", "timestamp"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<CandleDaily(ticker={self.ticker}, timestamp={self.timestamp}, close={self.close})>"


class PriceData(Base):
    """가격 데이터 모델

    Attributes:
        id: 기본 키
        timestamp: 가격 시각 (UTC)
        symbol: 심볼 (예: USD-KRW, GOLD-KRW)
        price: 가격
        source: 데이터 소스 (yfinance, hantu, fdr 등)
    """

    __tablename__ = "price_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        # 중복 방지: 같은 시간, 같은 심볼, 같은 소스는 하나만
        UniqueConstraint("timestamp", "symbol", "source", name="uix_timestamp_symbol_source"),
        # 조회 성능 최적화를 위한 복합 인덱스
        Index("idx_symbol_source_timestamp", "symbol", "source", "timestamp"),
    )

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<PriceData(symbol={self.symbol}, source={self.source}, timestamp={self.timestamp}, price={self.price})>"
