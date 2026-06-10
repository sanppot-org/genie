"""Tests for DividendSyncService."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDividend, Ticker
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.ticker_repository import TickerRepository
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.dividend import DividendKind, DividendOutput
from src.service.dividend_sync_service import DividendSyncService


@pytest.fixture
def kr_stock_ticker(session: Session) -> Ticker:
    repo = TickerRepository(session)
    return repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))


def _make_service(session: Session, rows: list[DividendOutput]) -> tuple[DividendSyncService, MagicMock]:
    client = MagicMock(spec=HantuDomesticAPI)
    client.get_dividend_history.return_value = rows
    service = DividendSyncService(
        client=client,
        ticker_repository=TickerRepository(session),
        dividend_repository=StockDividendRepository(session),
    )
    return service, client


class TestDividendSyncService:
    def test_sync_calls_kis_once_with_all_and_maps_divi_kind(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """GB1=ALL 단일 호출 + 응답 divi_kind 한글 라벨을 DB 라벨로 매핑."""
        rows = [
            DividendOutput(
                sht_cd="005930", record_date="20241227", divi_pay_dt="20250417",
                per_sto_divi_amt="361", divi_kind="결산",
            ),
            DividendOutput(
                sht_cd="005930", record_date="20240630", divi_pay_dt="20240820",
                per_sto_divi_amt="361", divi_kind="중간",
            ),
            DividendOutput(
                sht_cd="005930", record_date="20240331", divi_pay_dt="20240520",
                per_sto_divi_amt="361", divi_kind="분기",
            ),
        ]
        service, client = _make_service(session, rows)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        # 호출 횟수 1회 + GB1=ALL
        assert client.get_dividend_history.call_count == 1
        kwargs = client.get_dividend_history.call_args.kwargs
        assert kwargs["kind"] is DividendKind.ALL

        assert result.received == 3
        assert result.upserted == 3
        assert result.skipped_unmapped == 0
        assert result.skipped_invalid == 0
        assert result.collapsed_duplicates == 0

        stored = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        kind_by_date = {r.record_date: r.kind for r in stored}
        assert kind_by_date == {
            date(2024, 12, 27): "SETTLE",
            date(2024, 6, 30): "INTERIM",
            date(2024, 3, 31): "QUARTERLY",
        }

    def test_sync_collapses_duplicate_kind_for_same_event(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """KIS가 동일 (record_date, dps)를 '중간'·'분기' 두 라벨로 응답하면 QUARTERLY만 남는다."""
        rows = [
            DividendOutput(
                sht_cd="005930", record_date="20240331",
                per_sto_divi_amt="361", divi_kind="중간",
            ),
            DividendOutput(
                sht_cd="005930", record_date="20240331",
                per_sto_divi_amt="361", divi_kind="분기",
            ),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.received == 2
        assert result.upserted == 1
        assert result.collapsed_duplicates == 1

        stored = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert len(stored) == 1
        assert stored[0].kind == "QUARTERLY"

    def test_sync_preserves_same_date_different_dps(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """같은 record_date라도 dps가 다르면 별도 이벤트로 모두 보존."""
        rows = [
            DividendOutput(
                sht_cd="005930", record_date="20240331",
                per_sto_divi_amt="361", divi_kind="분기",
            ),
            DividendOutput(
                sht_cd="005930", record_date="20240331",
                per_sto_divi_amt="100", divi_kind="중간",
            ),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 2
        assert result.collapsed_duplicates == 0

    def test_sync_skips_unknown_divi_kind(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """divi_kind가 None / 공백 / 예상 외 한글이면 skipped_invalid로 카운트."""
        rows = [
            DividendOutput(sht_cd="005930", record_date="20241227", per_sto_divi_amt="100", divi_kind=None),
            DividendOutput(sht_cd="005930", record_date="20240930", per_sto_divi_amt="100", divi_kind=""),
            DividendOutput(sht_cd="005930", record_date="20240630", per_sto_divi_amt="100", divi_kind="기타"),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.received == 3
        assert result.upserted == 0
        assert result.skipped_invalid == 3
        assert StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id) == []

    def test_sync_skips_unmapped_ticker(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """tickers에 없는 종목코드는 skipped_unmapped로 카운트."""
        rows = [
            DividendOutput(
                sht_cd="999999", record_date="20241227",
                per_sto_divi_amt="500", divi_kind="결산",
            ),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 0
        assert result.skipped_unmapped == 1

    def test_sync_skips_row_with_missing_record_date_or_dps(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """record_date / dps가 빈 값이면 skipped_invalid."""
        rows = [
            DividendOutput(
                sht_cd="005930", record_date="",
                per_sto_divi_amt="500", divi_kind="결산",
            ),
            DividendOutput(
                sht_cd="005930", record_date="20241227",
                per_sto_divi_amt="", divi_kind="결산",
            ),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 0
        assert result.skipped_invalid == 2

    def test_sync_skips_zero_dps_no_dividend_resolution(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """dps=0인 KSD 무배당 결의 이력은 적재하지 않는다."""
        rows = [
            DividendOutput(
                sht_cd="005930", record_date="19991231",
                per_sto_divi_amt="0", divi_kind="결산",
            ),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(1999, 1, 1), date(1999, 12, 31))

        assert result.upserted == 0
        assert result.skipped_invalid == 1

    def test_sync_parses_slash_formatted_pay_date(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """KIS가 divi_pay_dt를 'YYYY/MM/DD'로 보내도 pay_date에 정상 적재."""
        rows = [
            DividendOutput(
                sht_cd="005930", record_date="20241231", divi_pay_dt="2025/04/18",
                per_sto_divi_amt="363", divi_kind="결산",
            ),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 1
        stored = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert stored[0].pay_date == date(2025, 4, 18)

    def test_sync_is_idempotent(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """같은 기간 두 번 호출해도 row 수는 그대로, dps만 덮어쓰기."""
        first = [
            DividendOutput(
                sht_cd="005930", record_date="20241227",
                per_sto_divi_amt="361", divi_kind="결산",
            ),
        ]
        _make_service(session, first)[0].sync(date(2024, 1, 1), date(2024, 12, 31))

        second = [
            DividendOutput(
                sht_cd="005930", record_date="20241227",
                per_sto_divi_amt="400", divi_kind="결산",
            ),
        ]
        _make_service(session, second)[0].sync(date(2024, 1, 1), date(2024, 12, 31))

        rows: list[StockDividend] = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert len(rows) == 1
        assert rows[0].dps == 400.0


class TestFiscalYearReformCorrection:
    """배당절차 개선: 봄 결산배당의 fiscal_year를 placeholder 앵커로 직전 회계연도에 귀속."""

    def _fy_by_date(self, session: Session, ticker_id: int) -> dict[date, int]:
        rows = StockDividendRepository(session).find_by_ticker(ticker_id)
        return {r.record_date: r.fiscal_year for r in rows}

    def test_reform_spring_settle_anchored_to_prev_year(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """`(N-1)-12-31 dps=0` placeholder가 있으면 봄(1~6월) 결산배당은 fiscal_year=N-1.

        placeholder 자체는 적재되지 않는다(앵커 전용).
        """
        rows = [
            DividendOutput(sht_cd="005930", record_date="20241231", per_sto_divi_amt="130", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20251231", per_sto_divi_amt="0", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20260415", per_sto_divi_amt="150", divi_kind="결산"),
        ]
        service, _ = _make_service(session, rows)

        result = service.sync(date(2024, 12, 1), date(2026, 6, 30))

        assert result.upserted == 2  # placeholder(dps=0) 제외
        fy = self._fy_by_date(session, kr_stock_ticker.id)
        assert fy == {date(2024, 12, 31): 2024, date(2026, 4, 15): 2025}

    def test_always_spring_without_placeholder_not_adjusted(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """폐지 placeholder가 없는 상시 봄 결산형은 보정하지 않는다(record_date.year 유지)."""
        rows = [
            DividendOutput(sht_cd="005930", record_date="20240331", per_sto_divi_amt="20", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20260331", per_sto_divi_amt="20", divi_kind="결산"),
        ]
        service, _ = _make_service(session, rows)

        service.sync(date(2024, 1, 1), date(2026, 6, 30))

        fy = self._fy_by_date(session, kr_stock_ticker.id)
        assert fy == {date(2024, 3, 31): 2024, date(2026, 3, 31): 2026}

    def test_mixed_old_dec_and_reform_spring(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """봄 배당만 보정하고 같은 해 12월 실배당은 record_date.year 유지 → 연속 회계연도."""
        rows = [
            DividendOutput(sht_cd="005930", record_date="20231231", per_sto_divi_amt="0", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20240331", per_sto_divi_amt="400", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20241231", per_sto_divi_amt="100", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20251231", per_sto_divi_amt="0", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20260303", per_sto_divi_amt="550", divi_kind="결산"),
        ]
        service, _ = _make_service(session, rows)

        service.sync(date(2023, 12, 1), date(2026, 6, 30))

        fy = self._fy_by_date(session, kr_stock_ticker.id)
        assert fy == {
            date(2024, 3, 31): 2023,   # placeholder 2023 → 직전 귀속
            date(2024, 12, 31): 2024,  # 12월 실배당, 미보정
            date(2026, 3, 3): 2025,    # placeholder 2025 → 직전 귀속
        }

    def test_interim_spring_not_adjusted(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """중간/분기 배당은 placeholder가 있어도 보정 대상이 아니다(결산만 보정)."""
        rows = [
            DividendOutput(sht_cd="005930", record_date="20251231", per_sto_divi_amt="0", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20260331", per_sto_divi_amt="50", divi_kind="분기"),
        ]
        service, _ = _make_service(session, rows)

        service.sync(date(2025, 12, 1), date(2026, 6, 30))

        fy = self._fy_by_date(session, kr_stock_ticker.id)
        assert fy == {date(2026, 3, 31): 2026}

    def test_dec31_only_placeholder_anchors(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """12월이라도 31일이 아닌 dps=0 결산은 폐지 placeholder가 아니다(앵커 미작동)."""
        rows = [
            DividendOutput(sht_cd="005930", record_date="20251220", per_sto_divi_amt="0", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20260415", per_sto_divi_amt="150", divi_kind="결산"),
        ]
        service, _ = _make_service(session, rows)

        service.sync(date(2025, 12, 1), date(2026, 6, 30))

        fy = self._fy_by_date(session, kr_stock_ticker.id)
        assert fy == {date(2026, 4, 15): 2026}  # placeholder 아님 → 미보정

    def test_resync_corrects_previously_mislabeled_row_in_place(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """placeholder 누락 배치로 fiscal_year=2026 오적재된 봄 배당이, placeholder 포함 광역
        재동기화 시 UPSERT로 fiscal_year=2025로 in-place 보정된다(백필 경로 검증)."""
        narrow = [
            DividendOutput(sht_cd="005930", record_date="20260415", per_sto_divi_amt="150", divi_kind="결산"),
        ]
        _make_service(session, narrow)[0].sync(date(2026, 3, 1), date(2026, 6, 30))
        assert self._fy_by_date(session, kr_stock_ticker.id) == {date(2026, 4, 15): 2026}

        wide = [
            DividendOutput(sht_cd="005930", record_date="20251231", per_sto_divi_amt="0", divi_kind="결산"),
            DividendOutput(sht_cd="005930", record_date="20260415", per_sto_divi_amt="150", divi_kind="결산"),
        ]
        _make_service(session, wide)[0].sync(date(2025, 12, 1), date(2026, 6, 30))

        stored = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert len(stored) == 1  # 중복 생성 없이 갱신
        assert self._fy_by_date(session, kr_stock_ticker.id) == {date(2026, 4, 15): 2025}
