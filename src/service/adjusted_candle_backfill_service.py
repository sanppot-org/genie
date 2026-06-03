"""KR 주식 수정주가(adjusted) 백필 서비스.

기존 `stock_daily_candles`의 원주가는 보존하고, 종목별로 네이버 수정주가를
조회해 `adj_*` 컬럼만 채운다(액면분할·무상증자 절벽 제거용).
"""

from dataclasses import dataclass
from datetime import date
import logging

from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_daily_candle_client import PykrxDailyCandleClient
from src.service.exceptions import ExceptionCode, GenieError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdjustedBackfillResult:
    """백필 결과 통계."""

    ticker: str
    fetched: int    # 네이버 수정주가 응답 row 수(거래정지 제외)
    updated: int    # 실제 adj_* 갱신된 DB row 수(기존 원주가 row와 날짜 매칭)
    from_date: date | None
    to_date: date | None


class AdjustedCandleBackfillService:
    """종목별 수정주가를 조회해 adj_* 컬럼을 채우는 백필."""

    def __init__(
        self,
        client: PykrxDailyCandleClient,
        ticker_repository: TickerRepository,
        daily_candle_repository: StockDailyCandleRepository,
    ) -> None:
        self._client = client
        self._tickers = ticker_repository
        self._candles = daily_candle_repository

    def backfill(self, ticker_code: str) -> AdjustedBackfillResult:
        """종목 코드의 수정주가를 기존 일봉 row에 매칭해 채운다. 종목 미발견 시 404."""
        ticker = self._tickers.find_by_ticker(ticker_code)
        if ticker is None:
            raise GenieError(code=ExceptionCode.NOT_FOUND, id=ticker_code)

        existing = self._candles.find_by_ticker(ticker.id)
        if not existing:
            logger.info("수정주가 백필 스킵: 원주가 row 없음 ticker=%s", ticker_code)
            return AdjustedBackfillResult(ticker=ticker_code, fetched=0, updated=0, from_date=None, to_date=None)

        from_date = existing[0].date
        to_date = existing[-1].date
        adjusted = self._client.fetch_adjusted_by_ticker(ticker_code, from_date, to_date)
        mapping = {a.date: (a.open, a.high, a.low, a.close, a.volume) for a in adjusted}
        updated = self._candles.update_adjusted(ticker.id, mapping)

        logger.info(
            "수정주가 백필 완료 ticker=%s range=%s~%s fetched=%d updated=%d",
            ticker_code, from_date, to_date, len(adjusted), updated,
        )
        return AdjustedBackfillResult(
            ticker=ticker_code,
            fetched=len(adjusted),
            updated=updated,
            from_date=from_date,
            to_date=to_date,
        )
