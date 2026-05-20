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

        stored = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        kind_by_date = {r.record_date: r.kind for r in stored}
        assert kind_by_date == {
            date(2024, 12, 27): "SETTLE",
            date(2024, 6, 30): "INTERIM",
            date(2024, 3, 31): "QUARTERLY",
        }

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
