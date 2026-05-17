"""펀더멘털 읽기 서비스 — ticker 코드 → 일자 범위 시계열."""

from datetime import date

from src.database.models import StockFundamental, Ticker
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.ticker_repository import TickerRepository
from src.service.exceptions import ExceptionCode, GenieError


class FundamentalService:
    """KR 주식 펀더멘털 시계열 조회 (쓰기는 `FundamentalSyncService`)."""

    def __init__(
            self,
            ticker_repository: TickerRepository,
            fundamental_repository: StockFundamentalRepository,
    ) -> None:
        self._tickers = ticker_repository
        self._fundamentals = fundamental_repository

    def get_time_series(
            self,
            ticker_code: str,
            from_date: date | None,
            to_date: date | None,
    ) -> tuple[Ticker, list[StockFundamental]]:
        """ticker 코드로 종목 + 일자 범위 펀더멘털 반환. 종목 미발견 시 404."""
        ticker = self._tickers.find_by_ticker(ticker_code)
        if ticker is None:
            raise GenieError(code=ExceptionCode.NOT_FOUND, id=ticker_code)
        rows = self._fundamentals.find_by_ticker(ticker.id, from_date, to_date)
        return ticker, rows
