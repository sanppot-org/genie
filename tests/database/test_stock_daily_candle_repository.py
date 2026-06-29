"""Tests for StockDailyCandleRepository.find_by_tickers — 멀티 티커 IN 로드."""

from datetime import date

from sqlalchemy.orm import Session

from src.database.models import StockDailyCandle
from src.database.stock_daily_candle_repository import StockDailyCandleRepository


def _candle(ticker_id: int, d: date, close: float) -> StockDailyCandle:
    return StockDailyCandle(
        date=d, ticker_id=ticker_id,
        open=close, high=close, low=close, close=close, volume=1000, trade_value=None,
    )


class TestFindByTickers:
    def _seed(self, session: Session) -> StockDailyCandleRepository:
        repo = StockDailyCandleRepository(session)
        repo.bulk_upsert([
            _candle(1, date(2024, 1, 2), 100),
            _candle(1, date(2024, 1, 3), 110),
            _candle(1, date(2024, 1, 4), 120),
            _candle(2, date(2024, 1, 3), 200),
            _candle(2, date(2024, 1, 4), 210),
        ])
        session.flush()
        return repo

    def test_여러티커_grouped_정렬(self, session: Session) -> None:
        repo = self._seed(session)

        result = repo.find_by_tickers([1, 2])

        assert set(result.keys()) == {1, 2}
        assert [c.close for c in result[1]] == [100, 110, 120]  # date asc
        assert [c.close for c in result[2]] == [200, 210]

    def test_단일조회_2회와_동일(self, session: Session) -> None:
        repo = self._seed(session)

        multi = repo.find_by_tickers([1, 2])

        assert [c.date for c in multi[1]] == [c.date for c in repo.find_by_ticker(1)]
        assert [c.date for c in multi[2]] == [c.date for c in repo.find_by_ticker(2)]

    def test_날짜_범위_필터(self, session: Session) -> None:
        repo = self._seed(session)

        result = repo.find_by_tickers([1, 2], from_date=date(2024, 1, 3), to_date=date(2024, 1, 3))

        assert [c.close for c in result[1]] == [110]
        assert [c.close for c in result[2]] == [200]

    def test_데이터없는_티커는_키없음(self, session: Session) -> None:
        repo = self._seed(session)

        result = repo.find_by_tickers([1, 999])

        assert 1 in result
        assert 999 not in result

    def test_빈_입력은_빈_dict(self, session: Session) -> None:
        repo = self._seed(session)

        assert repo.find_by_tickers([]) == {}
