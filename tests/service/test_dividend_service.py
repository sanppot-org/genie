"""Tests for DividendService (파생 지표 산정)."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDailyCandle, StockDividend, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
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
def candle_repo(session: Session) -> StockDailyCandleRepository:
    return StockDailyCandleRepository(session)


@pytest.fixture
def service(repo: StockDividendRepository, session: Session) -> DividendService:
    return DividendService(repo, TickerRepository(session), StockDailyCandleRepository(session))


def _candle(ticker_id: int, d: date, close: float, adj_close: float | None) -> StockDailyCandle:
    return StockDailyCandle(
        ticker_id=ticker_id, date=d,
        open=close, high=close, low=close, close=close, volume=1,
        adj_close=adj_close,
    )


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

    def test_split_year_does_not_break_streak_after_adjust(
            self, repo: StockDividendRepository, candle_repo: StockDailyCandleRepository,
            service: DividendService, ticker_id: int,
    ) -> None:
        """분할연도 보정: raw 연합산이면 분할 전 거액 DPS 때문에 인상이 감소로 오판되지만,
        record_date factor로 환산하면 실제 주당배당 증가 추세(300<350<400)가 드러난다.
        """
        # 2017 record는 분할 전(factor 0.02), 2018·2019는 분할 후(factor 1.0).
        candle_repo.save(_candle(ticker_id, date(2017, 12, 29), close=50000, adj_close=1000))
        candle_repo.save(_candle(ticker_id, date(2018, 12, 28), close=1000, adj_close=1000))
        candle_repo.save(_candle(ticker_id, date(2019, 12, 30), close=1100, adj_close=1100))
        repo.bulk_upsert([
            _row(ticker_id, date(2017, 12, 29), 15000),  # 보정 후 300
            _row(ticker_id, date(2018, 12, 28), 350),    # 350
            _row(ticker_id, date(2019, 12, 30), 400),    # 400
        ])
        # raw면 2018(350)<2017(15000) → streak 1. 보정하면 300<350<400 → streak 2.
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2020, 6, 1),
        ) == 2

    def test_split_crossing_records_within_one_fiscal_year_sum_correctly(
            self, repo: StockDividendRepository, candle_repo: StockDailyCandleRepository,
            service: DividendService, ticker_id: int,
    ) -> None:
        """같은 회계연도(FY2018)에 분할 전(factor 0.02)·후(factor 1.0) record가 공존해도,
        각 record가 오늘 주식수 기준으로 환산된 뒤 합산되므로 연배당이 올바르게 누적된다.
        커밋이 지목한 핵심 시나리오(삼성 FY2018: 5월 분할).
        """
        candle_repo.save(_candle(ticker_id, date(2017, 12, 29), close=50000, adj_close=1000))  # 0.02
        candle_repo.save(_candle(ticker_id, date(2018, 3, 30), close=50000, adj_close=1000))    # 0.02 분할 전
        candle_repo.save(_candle(ticker_id, date(2018, 12, 28), close=1000, adj_close=1000))     # 1.0 분할 후
        candle_repo.save(_candle(ticker_id, date(2019, 12, 30), close=1100, adj_close=1100))     # 1.0
        repo.bulk_upsert([
            _row(ticker_id, date(2017, 12, 29), 21500),                  # FY2017 보정 430
            _row(ticker_id, date(2018, 3, 30), 17700, kind="QUARTERLY"),  # FY2018 분할 전 → 354
            _row(ticker_id, date(2018, 12, 28), 354, kind="SETTLE"),      # FY2018 분할 후 → 354 (합 708)
            _row(ticker_id, date(2019, 12, 30), 800),                     # FY2019 보정 800
        ])
        # 보정: FY2017=430 < FY2018=708 < FY2019=800 → streak 2.
        # raw면 FY2018(18054) > FY2019(800) → 감소 → streak 0. 보정이 교차합산을 바로잡음.
        assert service.consecutive_dividend_increase_years(
            ticker_id, today=date(2020, 6, 1),
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

    def test_bulk_streak_uses_raw_dps_no_split_adjust(
            self,
            repo: StockDividendRepository,
            candle_repo: StockDailyCandleRepository,
            service: DividendService,
            ticker_id: int,
    ) -> None:
        """bulk는 성능상 분할 보정 미적용(원본 DPS 비교) — 알려진 한계 고정."""
        # 캔들에 분할 factor가 있어도 bulk는 무시하고 raw로 비교한다.
        candle_repo.save(_candle(ticker_id, date(2017, 12, 29), close=50000, adj_close=1000))
        candle_repo.save(_candle(ticker_id, date(2018, 12, 28), close=1000, adj_close=1000))
        repo.bulk_upsert([
            _row(ticker_id, date(2017, 12, 29), 15000),  # raw 비교: 다음 해보다 큼
            _row(ticker_id, date(2018, 12, 28), 350),    # raw 350 < 15000 → 감소로 처리
        ])
        # raw면 2018(350) < 2017(15000) → 인상 아님 → streak 0.
        # (단건 메서드라면 보정으로 300<350 → 1; bulk는 보정 안 하므로 0)
        result = service.consecutive_dividend_increase_years_bulk(
            [ticker_id], today=date(2019, 6, 1),
        )
        assert result == {ticker_id: 0}


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

    def test_split_adjusts_dps_to_today_share_base(
            self, repo: StockDividendRepository, candle_repo: StockDailyCandleRepository,
            service: DividendService, ticker_id: int,
    ) -> None:
        # 삼성 50:1 액면분할(2018-05): 분할 전 record_date는 factor=adj/close=0.02로 환산돼
        # 분할 후 DPS와 동일 좌표계로 연속화된다. 17,700 × 0.02 = 354.
        # bulk_upsert는 adj_* 컬럼을 안 쓰므로 save로 적재(원주가+수정주가 함께).
        candle_repo.save(_candle(ticker_id, date(2018, 3, 30), close=2607000, adj_close=52140))  # factor 0.02
        candle_repo.save(_candle(ticker_id, date(2018, 6, 29), close=51900, adj_close=51900))      # factor 1.0
        repo.bulk_upsert([
            _row(ticker_id, date(2018, 3, 30), 17700, kind="QUARTERLY"),
            _row(ticker_id, date(2018, 6, 29), 354, kind="QUARTERLY"),
        ])

        _, rows = service.get_history("005930")

        assert [round(r.dps, 2) for r in rows] == [354.0, 354.0]

    def test_keeps_raw_dps_when_adj_close_missing(
            self, repo: StockDividendRepository, candle_repo: StockDailyCandleRepository,
            service: DividendService, ticker_id: int,
    ) -> None:
        # adj_close 미백필(~2014 이전)이면 factor=1 → 원본 DPS 유지.
        candle_repo.save(_candle(ticker_id, date(2012, 12, 27), close=10000, adj_close=None))
        repo.bulk_upsert([_row(ticker_id, date(2012, 12, 27), 500)])

        _, rows = service.get_history("005930")

        assert [r.dps for r in rows] == [500.0]

    def test_keeps_raw_dps_when_record_predates_all_candles(
            self, repo: StockDividendRepository, candle_repo: StockDailyCandleRepository,
            service: DividendService, ticker_id: int,
    ) -> None:
        """record_date가 가장 이른 캔들보다 앞서면(bisect idx<0) factor=1 → 원본 DPS 유지."""
        candle_repo.save(_candle(ticker_id, date(2020, 1, 2), close=1000, adj_close=1000))
        repo.bulk_upsert([_row(ticker_id, date(2015, 12, 28), 600)])  # 캔들 이전

        _, rows = service.get_history("005930")

        assert [r.dps for r in rows] == [600.0]

    def test_unknown_ticker_raises_not_found(self, service: DividendService) -> None:
        from src.service.exceptions import ExceptionCode, GenieError
        with pytest.raises(GenieError) as exc_info:
            service.get_history("999999")
        assert exc_info.value.code == ExceptionCode.NOT_FOUND
