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
def service(repo: StockDividendRepository, session: Session) -> DividendService:
    return DividendService(repo, TickerRepository(session))


def _row(ticker_id: int, record_date: date, dps: float, kind: str = "SETTLE") -> StockDividend:
    return StockDividend(
        ticker_id=ticker_id, record_date=record_date, dps=dps,
        kind=kind, fiscal_year=record_date.year,
    )


class TestIsQuarterlyDividend:
    def test_returns_true_when_quarterly_row_exists_in_last_year(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """최근 1년에 QUARTERLY 라벨 row가 1건만 있어도 True."""
        repo.bulk_upsert([
            _row(ticker_id, date(2025, 3, 31), 100, kind="QUARTERLY"),
            _row(ticker_id, date(2025, 12, 27), 100, kind="SETTLE"),
        ])
        assert service.is_quarterly_dividend(ticker_id, today=date(2026, 1, 31)) is True

    def test_returns_false_for_annual_only(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        repo.bulk_upsert([_row(ticker_id, date(2025, 12, 27), 1000, kind="SETTLE")])
        assert service.is_quarterly_dividend(ticker_id, today=date(2026, 1, 31)) is False

    def test_returns_false_for_interim_only(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """중간(반기)배당만 있는 종목은 분기 아님."""
        repo.bulk_upsert([
            _row(ticker_id, date(2025, 6, 30), 500, kind="INTERIM"),
            _row(ticker_id, date(2025, 12, 27), 500, kind="SETTLE"),
        ])
        assert service.is_quarterly_dividend(ticker_id, today=date(2026, 1, 31)) is False

    def test_quarterly_row_outside_year_window_excluded(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """1년보다 더 과거의 QUARTERLY row는 무시."""
        repo.bulk_upsert([
            _row(ticker_id, date(2023, 6, 30), 100, kind="QUARTERLY"),
        ])
        assert service.is_quarterly_dividend(ticker_id, today=date(2026, 1, 31)) is False


class TestConsecutiveDividendIncreaseYears:
    def test_continuous_increase_returns_count(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """2021→2022→2023 모두 인상이면 2 (전년 대비 비교 횟수).

        recency 앵커 때문에 최신 데이터(2023)가 cutoff_year여야 하므로 today=2024-05 고정.
        """
        repo.bulk_upsert([
            _row(ticker_id, date(2021, 12, 27), 100),
            _row(ticker_id, date(2022, 12, 27), 110),
            _row(ticker_id, date(2023, 12, 27), 120),
        ])
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2024, 5, 20),
        ) == 2

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
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2025, 5, 20),
        ) == 2

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
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2025, 5, 20),
        ) == 2

    def test_no_dividends_returns_zero(
            self, service: DividendService, ticker_id: int,
    ) -> None:
        assert service.consecutive_dividend_increase_years(ticker_id) == 0

    def test_gap_year_breaks_streak(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """배당 중단(연도 누락)은 연속을 끊는다 — 최근 연속분만 인정.

        2023 배당 중단(row 없음)으로 2024↔2022가 단절 → 최신 2025↑2024(+1)만 인정.
        """
        repo.bulk_upsert([
            _row(ticker_id, date(2021, 12, 27), 100),
            _row(ticker_id, date(2022, 12, 27), 110),
            # 2023 배당 중단 (dps<=0은 sync에서 적재되지 않아 결측)
            _row(ticker_id, date(2024, 12, 27), 120),
            _row(ticker_id, date(2025, 12, 27), 130),
        ])
        # cutoff=2025, years_desc=[2025,2024,2022,2021]: 2025↑2024(+1), 2024↔2022 단절→break
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2026, 5, 20),
        ) == 1

    def test_stale_streak_returns_zero(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """과거에 인상했어도 최근 완료 회계연도에 배당이 없으면 0 (recency 앵커)."""
        repo.bulk_upsert([
            _row(ticker_id, date(2018, 12, 27), 100),
            _row(ticker_id, date(2019, 12, 27), 110),
            _row(ticker_id, date(2020, 12, 27), 120),
            # 2021~ 배당 완전 중단
        ])
        # today=2026-05 → cutoff=2025, 최신 데이터 연도 2020 != 2025 → 0
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2026, 5, 20),
        ) == 0

    def test_in_progress_fiscal_year_excluded_after_april(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """5월 이후: 진행 중인 올해(2026) fiscal_year row가 있어도 streak 계산에서 제외.

        2026년 1분기 배당(부분합)이 2025년 연간보다 작아서 'break' 시키지 않도록 함.
        """
        repo.bulk_upsert([
            _row(ticker_id, date(2023, 12, 27), 1000),
            _row(ticker_id, date(2024, 12, 27), 1200),
            _row(ticker_id, date(2025, 12, 27), 1444),
            _row(ticker_id, date(2026, 3, 31), 361, kind="QUARTERLY"),  # 진행 중 부분합
        ])
        # cutoff=2025 → 2025↑2024↑2023 → streak = 2 (2026은 무시)
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2026, 5, 20),
        ) == 2

    def test_in_progress_fiscal_year_excluded_before_may(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        """4월 이전: 작년치도 아직 미마감이므로 재작년까지만 비교."""
        repo.bulk_upsert([
            _row(ticker_id, date(2023, 12, 27), 1000),
            _row(ticker_id, date(2024, 12, 27), 1200),
            _row(ticker_id, date(2025, 12, 27), 800),   # 미완 (감소처럼 보이지만 제외돼야)
            _row(ticker_id, date(2026, 3, 31), 100, kind="QUARTERLY"),  # 미완
        ])
        # 2026-03-20 → cutoff=2024 → 2024↑2023만 비교 → streak = 1
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2026, 3, 20),
        ) == 1

    def test_bulk_respects_today_param(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        repo.bulk_upsert([
            _row(ticker_id, date(2024, 12, 27), 1000),
            _row(ticker_id, date(2025, 12, 27), 1100),
            _row(ticker_id, date(2026, 3, 31), 200, kind="QUARTERLY"),  # 진행 중
        ])
        result = service.consecutive_dividend_increase_years_bulk(
            [ticker_id], today=date(2026, 5, 20),
        )
        assert result == {ticker_id: 1}  # 2026 제외, 2025↑2024 = 1


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
        # ticker_id: 분기배당, other: 연 1회만
        repo.bulk_upsert([
            _row(ticker_id, date(2025, 3, 31), 100, kind="QUARTERLY"),
            _row(ticker_id, date(2025, 6, 30), 100, kind="QUARTERLY"),
            _row(ticker_id, date(2025, 9, 30), 100, kind="QUARTERLY"),
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
            [ticker_id, other_ticker_id], today=date(2024, 5, 20),
        )
        assert result == {ticker_id: 2, other_ticker_id: 0}

    def test_bulk_methods_handle_empty_input(self, service: DividendService) -> None:
        assert service.is_quarterly_dividend_bulk([]) == {}
        assert service.consecutive_dividend_increase_years_bulk([]) == {}


class TestGetHistory:
    """배당 지급 이력 조회 — 차트 표시용."""

    def test_returns_ticker_and_rows_sorted_by_record_date(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        repo.bulk_upsert([
            _row(ticker_id, date(2024, 6, 30), 361, kind="INTERIM"),
            _row(ticker_id, date(2024, 12, 27), 361, kind="SETTLE"),
            _row(ticker_id, date(2024, 3, 31), 361, kind="INTERIM"),
        ])

        ticker, rows = service.get_history("005930")

        assert ticker.ticker == "005930"
        assert ticker.name == "삼성전자"
        assert [r.record_date for r in rows] == [date(2024, 3, 31), date(2024, 6, 30), date(2024, 12, 27)]
        assert [r.kind for r in rows] == ["INTERIM", "INTERIM", "SETTLE"]

    def test_applies_date_filter(
            self, repo: StockDividendRepository, service: DividendService, ticker_id: int,
    ) -> None:
        repo.bulk_upsert([
            _row(ticker_id, date(2022, 12, 27), 1000),
            _row(ticker_id, date(2023, 12, 27), 1100),
            _row(ticker_id, date(2024, 12, 27), 1200),
        ])
        _, rows = service.get_history("005930", from_date=date(2023, 1, 1), to_date=date(2023, 12, 31))
        assert [r.dps for r in rows] == [1100]

    def test_no_rows_returns_empty_list(
            self, service: DividendService, ticker_id: int,  # ticker만 만들고 배당은 없음
    ) -> None:
        _, rows = service.get_history("005930")
        assert rows == []

    def test_unknown_ticker_raises_not_found(self, service: DividendService) -> None:
        from src.service.exceptions import ExceptionCode, GenieError
        with pytest.raises(GenieError) as exc_info:
            service.get_history("999999")
        assert exc_info.value.code == ExceptionCode.NOT_FOUND
