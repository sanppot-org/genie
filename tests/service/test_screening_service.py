"""Tests for ScreeningService — 5개 지표 점수 합산 + 정렬·페이지네이션."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import (
    StockBuybackEvent,
    StockCancellationEvent,
    StockDividend,
    StockFinancialRatio,
    StockFundamental,
    StockTreasuryStock,
    Ticker,
)
from src.database.stock_buyback_event_repository import StockBuybackEventRepository
from src.database.stock_cancellation_event_repository import StockCancellationEventRepository
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.stock_financial_ratio_repository import StockFinancialRatioRepository
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.stock_treasury_stock_repository import StockTreasuryStockRepository
from src.database.ticker_repository import TickerRepository
from src.service.dividend_service import DividendService
from src.service.screening_service import (
    ScreeningFilters,
    ScreeningService,
    score_annual_cancel_ratio,
    score_consecutive_increase,
    score_dividend_yield,
    score_pbr,
    score_per,
    score_quarterly_dividend,
    score_regular_buyback,
    score_treasury_holding,
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

    def test_score_regular_buyback(self) -> None:
        assert score_regular_buyback(True) == 7
        assert score_regular_buyback(False) == 0

    @pytest.mark.parametrize("ratio,expected", [
        (0.0, 0), (0.5, 0), (0.51, 3), (1.5, 3), (1.51, 5),
        (2.0, 5), (2.01, 8), (10.0, 8),
    ])
    def test_score_annual_cancel_ratio(self, ratio: float, expected: int) -> None:
        assert score_annual_cancel_ratio(ratio) == expected

    @pytest.mark.parametrize("ratio,expected", [
        (0.0, 5), (1.99, 4), (2.0, 2), (4.99, 2), (5.0, 0), (10.0, 0),
    ])
    def test_score_treasury_holding(self, ratio: float, expected: int) -> None:
        assert score_treasury_holding(ratio) == expected


@pytest.fixture
def screening_setup(session: Session) -> ScreeningService:
    """다종목 픽스처를 깔고 ScreeningService 인스턴스 반환."""
    ticker_repo = TickerRepository(session)
    fund_repo = StockFundamentalRepository(session)
    div_repo = StockDividendRepository(session)
    buyback_repo = StockBuybackEventRepository(session)
    cancel_repo = StockCancellationEventRepository(session)
    treasury_repo = StockTreasuryStockRepository(session)
    ratio_repo = StockFinancialRatioRepository(session)

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
        StockDividend(ticker_id=t1.id, record_date=date(2025, 3, 31), dps=20, kind="QUARTERLY", fiscal_year=2025),
        StockDividend(ticker_id=t1.id, record_date=date(2025, 6, 30), dps=20, kind="QUARTERLY", fiscal_year=2025),
        StockDividend(ticker_id=t1.id, record_date=date(2025, 9, 30), dps=20, kind="QUARTERLY", fiscal_year=2025),
        StockDividend(ticker_id=t1.id, record_date=date(2025, 12, 27), dps=20, kind="SETTLE", fiscal_year=2025),
    ] + [
        StockDividend(
            ticker_id=t1.id, record_date=date(y, 12, 27), dps=10 + y - 2014,
            kind="SETTLE", fiscal_year=y,
        )
        for y in range(2014, 2025)
    ])
    # A: 최근 1년 취득결정(①), 소각 30,000주(②), 발행 1,000,000 → 소각비율 3%(>2 → 8점),
    #    자사주 보유 1.0%(③ <2 → 4점).
    buyback_repo.bulk_upsert([StockBuybackEvent(
        ticker_id=t1.id, rcept_no="A-ACQ-1", event_type="ACQUISITION",
        resolution_date=date(2026, 1, 10),
    )])
    cancel_repo.bulk_upsert([StockCancellationEvent(
        ticker_id=t1.id, rcept_no="A-CXL-1", report_nm="주식소각결정",
        resolution_date=date(2026, 2, 1), common_shares=30_000, preferred_shares=0,
    )])
    treasury_repo.bulk_upsert([StockTreasuryStock(
        ticker_id=t1.id, stlm_dt=date(2025, 12, 31), reprt_code="11011",
        issued_shares=1_000_000, treasury_shares=10_000, treasury_ratio=1.0,
    )])
    # A: KIS 공식 최신 연간 ROE(202512)=17.07.
    ratio_repo.bulk_upsert([
        StockFinancialRatio(ticker_id=t1.id, stac_yymm="202512", roe=17.07),
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
    # C: treasury row 있음 & 보유 0주(ratio==0) → ③ 5점, raw 0.0. (소각 없으니 ② 0.0% → 0점)
    treasury_repo.bulk_upsert([StockTreasuryStock(
        ticker_id=t3.id, stlm_dt=date(2025, 12, 31), reprt_code="11011",
        issued_shares=500_000, treasury_shares=0, treasury_ratio=0.0,
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
        dividend_service=DividendService(div_repo, ticker_repo),
        buyback_event_repository=buyback_repo,
        cancellation_event_repository=cancel_repo,
        treasury_stock_repository=treasury_repo,
        financial_ratio_repository=ratio_repo,
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

        # 1위: A00001 (PER 20 + PBR 5 + 배당 10 + 분기 5 + 연속 5 + 매입소각 7 + 소각비율 8 + 보유 4 = 64)
        top = result.rows[0]
        assert top.ticker == "A00001"
        assert top.scores.per == 20
        assert top.scores.pbr == 5
        assert top.scores.dividend_yield == 10
        assert top.scores.quarterly_dividend == 5
        assert top.scores.consecutive_increase_years == 5
        assert top.scores.regular_buyback == 7        # 취득결정 + 소각 존재
        assert top.scores.annual_cancel_ratio == 8    # 30,000/1,000,000 = 3% > 2
        assert top.scores.treasury_holding == 4       # 보유 1.0% (<2)
        assert top.regular_buyback is True
        assert top.annual_cancel_ratio == 3.0
        assert top.treasury_ratio == 1.0
        # total은 breakdown 합과 일치
        s = top.scores
        assert top.total_score == (
            s.per + s.pbr + s.dividend_yield + s.quarterly_dividend
            + s.consecutive_increase_years + s.regular_buyback
            + s.annual_cancel_ratio + s.treasury_holding
        )
        assert top.total_score == 64

        # 정렬 검증: total_score 내림차순
        scores = [r.total_score for r in result.rows]
        assert scores == sorted(scores, reverse=True)

    def test_roe_uses_latest_annual_financial_ratio(
            self, screening_setup: ScreeningService,
    ) -> None:
        """ROE는 KIS 공식 연간 ROE(financial_ratio repo)를 주입. row 없는 종목은 None."""
        result = screening_setup.score_kr_stocks(target_date=date(2026, 5, 15))
        a = next(r for r in result.rows if r.ticker == "A00001")
        assert a.roe == 17.07   # KIS 공식 ROE (EPS/BPS 근사 아님)
        b = next(r for r in result.rows if r.ticker == "B00002")
        assert b.roe is None    # 재무비율 row 없음

    def test_loss_company_per_is_zero(
            self, screening_setup: ScreeningService,
    ) -> None:
        """적자 종목(PER=None)은 PER 점수 0 + 결과에 포함."""
        result = screening_setup.score_kr_stocks(target_date=date(2026, 5, 15))
        c = next(r for r in result.rows if r.ticker == "C00003")
        assert c.per is None
        assert c.scores.per == 0
        assert c.scores.pbr == 4   # 0.5 → 4
        # treasury row 있음 & 보유 0주 → ③ 5점, raw 0.0 (소각 없으니 ② 0.0% → 0점, raw 0.0)
        assert c.treasury_ratio == 0.0
        assert c.scores.treasury_holding == 5
        assert c.annual_cancel_ratio == 0.0
        assert c.scores.annual_cancel_ratio == 0
        assert c.total_score == 4 + 5   # pbr 4 + 보유 5

    def test_no_fundamental_row_yields_all_zero(
            self, screening_setup: ScreeningService,
    ) -> None:
        """해당 일자에 펀더멘털이 없는 종목은 전 점수 0."""
        result = screening_setup.score_kr_stocks(target_date=date(2026, 5, 15))
        d = next(r for r in result.rows if r.ticker == "D00004")
        assert d.per is None and d.pbr is None and d.dividend_yield is None
        assert d.total_score == 0

    def test_no_treasury_row_yields_zero_not_five(
            self, screening_setup: ScreeningService,
    ) -> None:
        """③ 회귀: treasury row 없는 종목은 보유비율 0점(5점 아님) + raw None.

        ② 발행주식수 미상이므로 소각비율도 0점 + raw None.
        """
        result = screening_setup.score_kr_stocks(target_date=date(2026, 5, 15))
        # B00002·D00004 모두 treasury row 없음.
        for code in ("B00002", "D00004"):
            row = next(r for r in result.rows if r.ticker == code)
            assert row.treasury_ratio is None
            assert row.scores.treasury_holding == 0
            assert row.annual_cancel_ratio is None
            assert row.scores.annual_cancel_ratio == 0

    def test_regular_buyback_via_cancellation_only(
            self, session: Session, screening_setup: ScreeningService,
    ) -> None:
        """① 소각만 있어도(취득결정 없이) 매입·소각 결정 7점."""
        ticker_repo = TickerRepository(session)
        cancel_repo = StockCancellationEventRepository(session)
        e = ticker_repo.save(Ticker(
            ticker="E00005", name="소각만한주",
            asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
        ))
        cancel_repo.bulk_upsert([StockCancellationEvent(
            ticker_id=e.id, rcept_no="E-CXL-1", report_nm="주식소각결정",
            resolution_date=date(2026, 3, 1), common_shares=5_000, preferred_shares=0,
        )])

        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), today=date(2026, 5, 18),
        )
        row = next(r for r in result.rows if r.ticker == "E00005")
        assert row.regular_buyback is True
        assert row.scores.regular_buyback == 7

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


class TestScoreKrStocksFiltering:
    """ScreeningFilters 동작 — 픽스처(A:per=4/pbr=0.25/div=8, B:12/1.5/2, C:null/0.5/null, D:전무) 활용."""

    def test_filter_per_max_excludes_higher_and_null(
            self, screening_setup: ScreeningService,
    ) -> None:
        """per_max=5 → A(4.0)만 통과. B(12.0)·C(null)·D(null) 모두 제외."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(per_max=5.0),
        )
        assert result.total == 1
        assert [r.ticker for r in result.rows] == ["A00001"]

    def test_filter_per_min_excludes_lower_and_null(
            self, screening_setup: ScreeningService,
    ) -> None:
        """per_min=10 → B(12.0)만 통과. A(4.0)·C(null)·D(null) 제외."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(per_min=10.0),
        )
        assert [r.ticker for r in result.rows] == ["B00002"]

    def test_filter_pbr_range(
            self, screening_setup: ScreeningService,
    ) -> None:
        """pbr 0.4~0.6 → C(0.5)만. A(0.25)·B(1.5)·D(null) 제외."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(pbr_min=0.4, pbr_max=0.6),
        )
        assert [r.ticker for r in result.rows] == ["C00003"]

    def test_filter_dividend_yield_min_excludes_low_and_null(
            self, screening_setup: ScreeningService,
    ) -> None:
        """dividend_yield_min=3.0 → A(8.0)만. B(2.0)·C(null)·D(null) 제외."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(dividend_yield_min=3.0),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]

    def test_filter_combination_intersects(
            self, screening_setup: ScreeningService,
    ) -> None:
        """여러 필터는 AND. per_max=10 + pbr_max=0.3 → A만."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(per_max=10.0, pbr_max=0.3),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]

    def test_filter_yields_empty_when_no_match(
            self, screening_setup: ScreeningService,
    ) -> None:
        """모든 종목이 컷되면 total=0, rows=[]."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(per_max=0.5),
        )
        assert result.total == 0
        assert result.rows == []

    def test_filter_none_is_unchanged(
            self, screening_setup: ScreeningService,
    ) -> None:
        """filters=None 시 기본 동작과 동일 (4개 전체)."""
        no_filter = screening_setup.score_kr_stocks(target_date=date(2026, 5, 15))
        empty_filter = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), filters=ScreeningFilters(),
        )
        assert no_filter.total == empty_filter.total == 4

    def test_filter_total_reflects_post_filter_count(
            self, screening_setup: ScreeningService,
    ) -> None:
        """페이지네이션 total은 필터 후 결과 길이를 반영."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(per_max=10.0),
            limit=10, offset=0,
        )
        assert result.total == 1
        assert len(result.rows) == 1


class TestScoreKrStocksSearch:
    """ScreeningFilters.q (ticker/name substring, 대소문자 무시) 동작."""

    def test_search_by_ticker_substring(
            self, screening_setup: ScreeningService,
    ) -> None:
        """ticker 부분일치: 'A00001' → A 한 종목."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(q="A00001"),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]

    def test_search_by_name_substring(
            self, screening_setup: ScreeningService,
    ) -> None:
        """name 부분일치: '기업' → C00003(적자기업) 한 종목."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(q="기업"),
        )
        assert [r.ticker for r in result.rows] == ["C00003"]

    def test_search_case_insensitive(
            self, screening_setup: ScreeningService,
    ) -> None:
        """소문자 입력도 대문자 ticker 매칭."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(q="a00001"),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]

    def test_search_no_match_returns_empty(
            self, screening_setup: ScreeningService,
    ) -> None:
        """매칭 없으면 total=0."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(q="존재하지않음"),
        )
        assert result.total == 0
        assert result.rows == []

    def test_search_whitespace_only_is_noop(
            self, screening_setup: ScreeningService,
    ) -> None:
        """공백만 입력은 noop (전체 4개)."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(q="   "),
        )
        assert result.total == 4

    def test_search_empty_string_is_noop(
            self, screening_setup: ScreeningService,
    ) -> None:
        """빈 문자열도 noop."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(q=""),
        )
        assert result.total == 4

    def test_search_combines_with_numeric_filters(
            self, screening_setup: ScreeningService,
    ) -> None:
        """다른 필터와 AND. per_max=10 + q='A' → A만(B는 per=12 컷)."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(per_max=10.0, q="A"),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]


class TestScoreKrStocksQuarterlyAndStreak:
    """quarterly_only / consecutive_years_min — A는 분기배당+장기 streak, 나머지는 모두 비분기 + streak=0."""

    def test_quarterly_only_keeps_only_quarterly(
            self, screening_setup: ScreeningService,
    ) -> None:
        """quarterly_only=True → A만 통과(나머지는 분기배당 아님)."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), today=date(2026, 5, 18),
            filters=ScreeningFilters(quarterly_only=True),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]

    def test_quarterly_only_false_is_noop(
            self, screening_setup: ScreeningService,
    ) -> None:
        """quarterly_only=False(기본) → 전체 4개 그대로."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(quarterly_only=False),
        )
        assert result.total == 4

    def test_consecutive_years_min_keeps_long_streak(
            self, screening_setup: ScreeningService,
    ) -> None:
        """consecutive_years_min=5 → A만(B/C/D는 streak=0)."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(consecutive_years_min=5),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]

    def test_consecutive_years_min_zero_is_noop(
            self, screening_setup: ScreeningService,
    ) -> None:
        """consecutive_years_min=0 → 모두 0 이상이라 전체 4개."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15),
            filters=ScreeningFilters(consecutive_years_min=0),
        )
        assert result.total == 4

    def test_combination_with_numeric_filters(
            self, screening_setup: ScreeningService,
    ) -> None:
        """quarterly_only + consecutive_years_min=3 + per_max=10 → A만."""
        result = screening_setup.score_kr_stocks(
            target_date=date(2026, 5, 15), today=date(2026, 5, 18),
            filters=ScreeningFilters(
                quarterly_only=True, consecutive_years_min=3, per_max=10.0,
            ),
        )
        assert [r.ticker for r in result.rows] == ["A00001"]


class TestScoreKrStocksEmptyDb:
    def test_returns_empty_result_when_no_fundamentals(
            self, session: Session,
    ) -> None:
        """펀더멘털 데이터가 전혀 없으면 빈 결과."""
        service = ScreeningService(
            ticker_repository=TickerRepository(session),
            fundamental_repository=StockFundamentalRepository(session),
            dividend_service=DividendService(
                StockDividendRepository(session), TickerRepository(session),
            ),
            buyback_event_repository=StockBuybackEventRepository(session),
            cancellation_event_repository=StockCancellationEventRepository(session),
            treasury_stock_repository=StockTreasuryStockRepository(session),
            financial_ratio_repository=StockFinancialRatioRepository(session),
        )
        result = service.score_kr_stocks()
        assert result.total == 0
        assert result.rows == []
        assert result.target_date is None
