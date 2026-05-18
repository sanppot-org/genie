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


def _make_service(session: Session, by_kind: dict[DividendKind, list[DividendOutput]]) -> DividendSyncService:
    client = MagicMock(spec=HantuDomesticAPI)

    def fake_history(
        from_date: date, to_date: date,
        ticker: str | None = None,
        kind: DividendKind = DividendKind.ALL,
    ) -> list[DividendOutput]:
        return by_kind.get(kind, [])

    client.get_dividend_history.side_effect = fake_history
    return DividendSyncService(
        client=client,
        ticker_repository=TickerRepository(session),
        dividend_repository=StockDividendRepository(session),
    )


class TestDividendSyncService:
    def test_sync_maps_kind_and_upserts_kr_stock(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """SETTLE / INTERIM 각각 호출하여 kind 라벨 부여 후 upsert."""
        by_kind = {
            DividendKind.SETTLE: [
                DividendOutput(
                    sht_cd="005930", record_date="20241227", divi_pay_dt="20250417",
                    per_sto_divi_amt="361", divi_rate="0.46", divi_aplc_yymm="202412",
                ),
            ],
            DividendKind.INTERIM: [
                DividendOutput(
                    sht_cd="005930", record_date="20240930", divi_pay_dt="20241120",
                    per_sto_divi_amt="361", divi_rate="0.45", divi_aplc_yymm="202409",
                ),
            ],
        }
        service = _make_service(session, by_kind)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.received == 2
        assert result.upserted == 2
        assert result.skipped_unmapped == 0
        assert result.skipped_invalid == 0

        rows = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert {r.kind for r in rows} == {"SETTLE", "INTERIM"}
        assert {r.record_date for r in rows} == {date(2024, 12, 27), date(2024, 9, 30)}

    def test_sync_skips_unmapped_ticker(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """tickers에 없는 종목코드는 skipped_unmapped로 카운트."""
        by_kind = {
            DividendKind.SETTLE: [
                DividendOutput(sht_cd="999999", record_date="20241227", per_sto_divi_amt="500"),
            ],
            DividendKind.INTERIM: [],
        }
        service = _make_service(session, by_kind)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 0
        assert result.skipped_unmapped == 1

    def test_sync_skips_row_with_missing_record_date(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """record_date / dps가 빈 값이면 skipped_invalid."""
        by_kind = {
            DividendKind.SETTLE: [
                DividendOutput(sht_cd="005930", record_date="", per_sto_divi_amt="500"),
                DividendOutput(sht_cd="005930", record_date="20241227", per_sto_divi_amt=""),
            ],
            DividendKind.INTERIM: [],
        }
        service = _make_service(session, by_kind)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 0
        assert result.skipped_invalid == 2

    def test_sync_skips_zero_dps_no_dividend_resolution(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """dps=0인 KSD 무배당 결의 이력은 적재하지 않는다."""
        by_kind = {
            DividendKind.SETTLE: [
                DividendOutput(sht_cd="005930", record_date="19991231", per_sto_divi_amt="0"),
            ],
            DividendKind.INTERIM: [],
        }
        service = _make_service(session, by_kind)

        result = service.sync(date(1999, 1, 1), date(1999, 12, 31))

        assert result.upserted == 0
        assert result.skipped_invalid == 1

    def test_sync_parses_slash_formatted_pay_date(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """KIS가 divi_pay_dt를 'YYYY/MM/DD'로 보내도 pay_date에 정상 적재."""
        by_kind = {
            DividendKind.SETTLE: [
                DividendOutput(
                    sht_cd="005930", record_date="20241231", divi_pay_dt="2025/04/18",
                    per_sto_divi_amt="363",
                ),
            ],
            DividendKind.INTERIM: [],
        }
        service = _make_service(session, by_kind)

        result = service.sync(date(2024, 1, 1), date(2024, 12, 31))

        assert result.upserted == 1
        rows = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert rows[0].pay_date == date(2025, 4, 18)

    def test_sync_is_idempotent(
            self, session: Session, kr_stock_ticker: Ticker,
    ) -> None:
        """같은 기간 두 번 호출해도 row 수는 그대로, dps만 덮어쓰기."""
        first = {
            DividendKind.SETTLE: [
                DividendOutput(sht_cd="005930", record_date="20241227", per_sto_divi_amt="361"),
            ],
            DividendKind.INTERIM: [],
        }
        _make_service(session, first).sync(date(2024, 1, 1), date(2024, 12, 31))

        second = {
            DividendKind.SETTLE: [
                DividendOutput(sht_cd="005930", record_date="20241227", per_sto_divi_amt="400"),
            ],
            DividendKind.INTERIM: [],
        }
        _make_service(session, second).sync(date(2024, 1, 1), date(2024, 12, 31))

        rows: list[StockDividend] = StockDividendRepository(session).find_by_ticker(kr_stock_ticker.id)
        assert len(rows) == 1
        assert rows[0].dps == 400.0
