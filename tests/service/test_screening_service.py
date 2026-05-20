"""Tests for ScreeningService — 5개 지표 점수 합산 + 정렬·페이지네이션."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDividend, StockFundamental, Ticker
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.ticker_repository import TickerRepository
from src.service.dividend_service import DividendService
from src.service.screening_service import (
    ScreeningService,
    score_consecutive_increase,
    score_dividend_yield,
    score_pbr,
    score_per,
    score_quarterly_dividend,
)


class TestScoreRules:
    """점수표 경계값 검증."""

    @pytest.mark.parametrize("per,expected", [
        (None, 0), (-1.0, 0), (0.0, 0),
        (4.99, 20), (5.0, 15), (7.99, 15),
        (8.0, 10), (9.99, 10), (10.0, 5), (50.0, 5),
    ])
    def test_score_per(self, per: float | None, expected: int) -> None:
        assert score_per(per) == expected

    @pytest.mark.parametrize("pbr,expected", [
        (None, 0), (0.0, 0),
        (0.29, 5), (0.3, 4), (0.59, 4), (0.6, 3), (0.99, 3), (1.0, 0), (2.0, 0),
    ])
    def test_score_pbr(self, pbr: float | None, expected: int) -> None:
        assert score_pbr(pbr) == expected

    @pytest.mark.parametrize("div,expected", [
        (None, 0), (0.0, 0),
        (1.0, 2), (3.0, 2), (3.01, 5), (5.0, 5), (5.01, 7), (7.0, 7), (7.01, 10),
    ])
    def test_score_dividend_yield(self, div: float | None, expected: int) -> None:
        assert score_dividend_yield(div) == expected

    def test_score_quarterly_dividend(self) -> None:
        assert score_quarterly_dividend(True) == 5
        assert score_quarterly_dividend(False) == 0

    @pytest.mark.parametrize("years,expected", [
        (0, 0), (2, 0), (3, 3), (4, 3), (5, 4), (9, 4), (10, 5), (20, 5),
    ])
    def test_score_consecutive_increase(self, years: int, expected: int) -> None:
        assert score_consecutive_increase(years) == expected


@pytest.fixture
def screening_setup(session: Session) -> ScreeningService:
    """다종목 픽스처를 깔고 ScreeningService 인스턴스 반환."""
    ticker_repo = TickerRepository(session)
    fund_repo = StockFundamentalRepository(session)
    div_repo = StockDividendRepository(session)

    target_date = date(2026, 5, 15)

    # 최고 점수: 저PER, 저PBR, 고배당, 분기, 연속 인상 10년+
    t1 = ticker_repo.save(Ticker(
        ticker="A00001", name="저평가고배당주",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    fund_repo.bulk_upsert([StockFundamental(
        ticker_id=t1.id, date=target_date, per=4.0, pbr=0.25, div=8.0, eps=1000, bps=4000, dps=80,
    )])
    div_repo.bulk_upsert([
        StockDividend(ticker_id=t1.id, record_date=date(2025, 3, 31), dps=20, kind="INTERIM", fiscal_year=2025),
        StockDividend(ticker_id=t1.id, record_date=date(2025, 6, 30), dps=20, kind="INTERIM", fiscal_year=2025),
        StockDividend(ticker_id=t1.id, record_date=date(2025, 9, 30), dps=20, kind="INTERIM", fiscal_year=2025),
        StockDividend(ticker_id=t1.id, record_date=date(2025, 12, 27), dps=20, kind="SETTLE", fiscal_year=2025),
    ] + [
        StockDividend(
            ticker_id=t1.id, record_date=date(y, 12, 27), dps=10 + y - 2014,
            kind="SETTLE", fiscal_year=y,
        )
        for y in range(2014, 2025)
    ])

    # 중간 점수: 평균 PER, PBR 1.0 (PBR 0점), 보통 배당
    t2 = ticker_repo.save(Ticker(
        ticker="B00002", name="평범한주식",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    fund_repo.bulk_upsert([StockFundamental(
        ticker_id=t2.id, date=target_date, per=12.0, pbr=1.5, div=2.0, eps=2000, bps=15000, dps=400,
    )])

    # 적자 종목: PER=None, PBR=낮음, 배당 없음
    t3 = ticker_repo.save(Ticker(
        ticker="C00003", name="적자기업",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    fund_repo.bulk_upsert([StockFundamental(
        ticker_id=t3.id, date=target_date, per=None, pbr=0.5, div=None, eps=None, bps=8000, dps=None,
    )])

    # 펀더멘털 없음: 모든 점수 0 (특정일 데이터 누락 케이스)
    ticker_repo.save(Ticker(
        ticker="D00004", name="데이터없는주",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))

    # 비-KR_STOCK은 제외돼야 함
    ticker_repo.save(Ticker(
        ticker="KRW-BTC", name="비트코인",
        asset_type=AssetType.CRYPTO, data_source=DataSource.UPBIT.value,
    ))

    return ScreeningService(
        ticker_repository=ticker_repo,
        fundamental_repository=fund_repo,
        dividend_service=DividendService(div_repo),
    )


class TestScoreKrStocks:
    def test_returns_kr_stocks_only_sorted_by_total_desc(
            self, screening_setup: ScreeningService,
    ) -> None:
        """KR_STOCK만 포함하고 total_score DESC, ticker ASC로 정렬."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), today=date(2026, 5, 18),
        )

        # 비-KR_STOCK 제외 (4개)
        assert result.total == 4
        assert {r.ticker for r in result.rows} == {"A00001", "B00002", "C00003", "D00004"}

        # 1위: A00001 (저PER 20 + 저PBR 5 + 고배당 10 + 분기 5 + 10년+ 5 = 45)
        top = result.rows[0]
        assert top.ticker == "A00001"
        assert top.total_score == 45
        assert top.scores.per == 20
        assert top.scores.pbr == 5
        assert top.scores.dividend_yield == 10
        assert top.scores.quarterly_dividend == 5
        assert top.scores.consecutive_increase_years == 5

        # 정렬 검증: total_score 내림차순
        scores = [r.total_score for r in result.rows]
        assert scores == sorted(scores, reverse=True)

    def test_loss_company_per_is_zero(
            self, screening_setup: ScreeningService,
    ) -> None:
        """적자 종목(PER=None)은 PER 점수 0 + 결과에 포함."""
        result = screening_setup.score_kr_stocks(target_date=date(2026, 5, 15))
        c = next(r for r in result.rows if r.ticker == "C00003")
        assert c.per is None
        assert c.scores.per == 0
        assert c.scores.pbr == 4   # 0.5 → 4
        assert c.total_score == 4

    def test_no_fundamental_row_yields_all_zero(
            self, screening_setup: ScreeningService,
    ) -> None:
        """해당 일자에 펀더멘털이 없는 종목은 전 점수 0."""
        result = screening_setup.score_kr_stocks(target_date=date(2026, 5, 15))
        d = next(r for r in result.rows if r.ticker == "D00004")
        assert d.per is None and d.pbr is None and d.dividend_yield is None
        assert d.total_score == 0

    def test_pagination(self, screening_setup: ScreeningService) -> None:
        """limit/offset이 정렬된 전체 결과를 슬라이스."""
        first_page = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), limit=2, offset=0,
        )
        second_page = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), limit=2, offset=2,
        )

        assert first_page.total == 4
        assert second_page.total == 4
        assert len(first_page.rows) == 2
        assert len(second_page.rows) == 2
        # 페이지 간 중복 없음
        assert {r.ticker for r in first_page.rows} & {r.ticker for r in second_page.rows} == set()

    def test_target_date_defaults_to_latest_when_none(
            self, screening_setup: ScreeningService,
    ) -> None:
        """target_date=None 시 stock_fundamentals 최신 일자(=2026-05-15) 사용."""
        result = screening_setup.score_kr_stocks(target_date=None)
        assert result.target_date == date(2026, 5, 15)
        assert result.total == 4


class TestScoreKrStocksSorting:
    """sort_by/order 동작 검증 — 픽스처(A00001..D00004) 활용."""

    def test_sort_by_per_asc_puts_nulls_last(
            self, screening_setup: ScreeningService,
    ) -> None:
        """PER ASC: A(4.0)→B(12.0)→C(null)→D(null). null은 끝, 동률은 ticker ASC."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), sort_by="per", order="asc",
        )
        assert [r.ticker for r in result.rows] == ["A00001", "B00002", "C00003", "D00004"]

    def test_sort_by_per_desc_puts_nulls_last(
            self, screening_setup: ScreeningService,
    ) -> None:
        """PER DESC: B(12.0)→A(4.0)→C(null)→D(null). DESC에서도 null은 끝."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), sort_by="per", order="desc",
        )
        assert [r.ticker for r in result.rows] == ["B00002", "A00001", "C00003", "D00004"]

    def test_sort_by_ticker_asc_is_natural_order(
            self, screening_setup: ScreeningService,
    ) -> None:
        """ticker ASC: 종목코드 사전순 — 정렬 해제 상태의 정의."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), sort_by="ticker", order="asc",
        )
        assert [r.ticker for r in result.rows] == ["A00001", "B00002", "C00003", "D00004"]

    def test_sort_by_ticker_desc(
            self, screening_setup: ScreeningService,
    ) -> None:
        """ticker DESC: 종목코드 역순."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), sort_by="ticker", order="desc",
        )
        assert [r.ticker for r in result.rows] == ["D00004", "C00003", "B00002", "A00001"]

    def test_default_sort_unchanged(
            self, screening_setup: ScreeningService,
    ) -> None:
        """파라미터 미지정 시 기존 동작(total_score DESC, ticker ASC) 그대로."""
        default_result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), today=date(2026, 5, 18),
        )
        explicit_result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), today=date(2026, 5, 18),
            sort_by="total_score", order="desc",
        )
        assert [r.ticker for r in default_result.rows] == [r.ticker for r in explicit_result.rows]


class TestScoreKrStocksEmptyDb:
    def test_returns_empty_result_when_no_fundamentals(
            self, session: Session,
    ) -> None:
        """펀더멘털 데이터가 전혀 없으면 빈 결과."""
        service = ScreeningService(
            ticker_repository=TickerRepository(session),
            fundamental_repository=StockFundamentalRepository(session),
            dividend_service=DividendService(StockDividendRepository(session)),
        )
        result = service.score_kr_stocks()
        assert result.total == 0
        assert result.rows == []
        assert result.target_date is None
