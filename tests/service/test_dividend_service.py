"""Tests for DividendService (파생 지표 산정)."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDividend, Ticker
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.ticker_repository import TickerRepository
from src.service.dividend_service import DividendService


@pytest.fixture
def ticker_id(session: Session) -> int:
    repo = TickerRepository(session)
    ticker = repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    return ticker.id


@pytest.fixture
def repo(session: Session) -> StockDividendRepository:
    return StockDividendRepository(session)


@pytest.fixture
def service(repo: StockDividendRepository) -> DividendService:
    return DividendService(repo)


def _row(ticker_id: int, record_date: date, dps: float, kind: str = "SETTLE") -> StockDividend:
    return StockDividend(
        ticker_id=ticker_id, record_date=record_date, dps=dps,
        kind=kind, fiscal_year=record_date.year,
    )


class TestIsQuarterlyDividend:
    def test_returns_true_when_three_or_more_payments_in_last_year(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        repo.bulk_upsert([
            _row(ticker_id, date(2025, 3, 31), 100, kind="INTERIM"),
            _row(ticker_id, date(2025, 6, 30), 100, kind="INTERIM"),
            _row(ticker_id, date(2025, 9, 30), 100, kind="INTERIM"),
            _row(ticker_id, date(2025, 12, 27), 100, kind="SETTLE"),
        ])
        assert service.is_quarterly_dividend(ticker_id, today=date(2026, 1, 31)) is True

    def test_returns_false_for_annual_only(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        repo.bulk_upsert([_row(ticker_id, date(2025, 12, 27), 1000, kind="SETTLE")])
        assert service.is_quarterly_dividend(ticker_id, today=date(2026, 1, 31)) is False


class TestConsecutiveDividendIncreaseYears:
    def test_continuous_increase_returns_count(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """2021→2022→2023 모두 인상이면 2 (전년 대비 비교 횟수)."""
        repo.bulk_upsert([
            _row(ticker_id, date(2021, 12, 27), 100),
            _row(ticker_id, date(2022, 12, 27), 110),
            _row(ticker_id, date(2023, 12, 27), 120),
        ])
        assert service.consecutive_dividend_increase_years(ticker_id) == 2

    def test_freeze_keeps_streak_but_not_count_as_increase(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """동결은 연속을 끊지 않지만 인상 카운트엔 포함되지 않음.

        2020(100) → 2021(110:인상) → 2022(110:동결) → 2023(120:인상) → 2024(120:동결)
        최신부터: 2024→2023(동결, +0) → 2023→2022(인상, +1) → 2022→2021(동결, +0) → 2021→2020(인상, +1)
        합계 2.
        """
        repo.bulk_upsert([
            _row(ticker_id, date(2020, 12, 27), 100),
            _row(ticker_id, date(2021, 12, 27), 110),
            _row(ticker_id, date(2022, 12, 27), 110),
            _row(ticker_id, date(2023, 12, 27), 120),
            _row(ticker_id, date(2024, 12, 27), 120),
        ])
        assert service.consecutive_dividend_increase_years(ticker_id) == 2

    def test_decrease_breaks_streak(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """감소가 발생하면 그 시점부터 연속이 끊긴다 (최신부터 봤을 때)."""
        repo.bulk_upsert([
            _row(ticker_id, date(2021, 12, 27), 100),
            _row(ticker_id, date(2022, 12, 27), 90),   # 감소
            _row(ticker_id, date(2023, 12, 27), 110),  # 인상
            _row(ticker_id, date(2024, 12, 27), 120),  # 인상
        ])
        # 2024→2023(+1), 2023→2022(+1), 2022→2021(감소 → break)
        assert service.consecutive_dividend_increase_years(ticker_id) == 2

    def test_no_dividends_returns_zero(
            self, service: DividendService, ticker_id: int,
    ) -> None:
        assert service.consecutive_dividend_increase_years(ticker_id) == 0


class TestBulkMethods:
    """다건 ticker 일괄 처리 — 단건 메서드와 동일한 결과를 쿼리 1회로."""

    @pytest.fixture
    def other_ticker_id(self, session: Session) -> int:
        repo = TickerRepository(session)
        ticker = repo.save(Ticker(
            ticker="035420", name="NAVER",
            asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
        ))
        return ticker.id

    def test_is_quarterly_dividend_bulk_returns_per_ticker_flags(
            self,
            repo: StockDividendRepository,
            service: DividendService,
            ticker_id: int,
            other_ticker_id: int,
    ) -> None:
        # ticker_id: 분기(4건), other: 연 1회만
        repo.bulk_upsert([
            _row(ticker_id, date(2025, 3, 31), 100, kind="INTERIM"),
            _row(ticker_id, date(2025, 6, 30), 100, kind="INTERIM"),
            _row(ticker_id, date(2025, 9, 30), 100, kind="INTERIM"),
            _row(ticker_id, date(2025, 12, 27), 100, kind="SETTLE"),
            _row(other_ticker_id, date(2025, 12, 27), 1000, kind="SETTLE"),
        ])

        result = service.is_quarterly_dividend_bulk(
            [ticker_id, other_ticker_id], today=date(2026, 1, 31),
        )
        assert result == {ticker_id: True, other_ticker_id: False}

    def test_consecutive_increase_years_bulk_returns_per_ticker_streak(
            self,
            repo: StockDividendRepository,
            service: DividendService,
            ticker_id: int,
            other_ticker_id: int,
    ) -> None:
        repo.bulk_upsert([
            # ticker_id: 2년 연속 인상
            _row(ticker_id, date(2021, 12, 27), 100),
            _row(ticker_id, date(2022, 12, 27), 110),
            _row(ticker_id, date(2023, 12, 27), 120),
            # other_ticker_id: 데이터 없음 → 0
        ])

        result = service.consecutive_dividend_increase_years_bulk(
            [ticker_id, other_ticker_id],
        )
        assert result == {ticker_id: 2, other_ticker_id: 0}

    def test_bulk_methods_handle_empty_input(self, service: DividendService) -> None:
        assert service.is_quarterly_dividend_bulk([]) == {}
        assert service.consecutive_dividend_increase_years_bulk([]) == {}
