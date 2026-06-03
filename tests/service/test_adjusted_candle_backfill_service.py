"""Tests for AdjustedCandleBackfillService."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDailyCandle, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_daily_candle_client import PykrxAdjustedCandle, PykrxDailyCandleClient
from src.service.adjusted_candle_backfill_service import AdjustedCandleBackfillService
from src.service.exceptions import GenieError


@pytest.fixture
def samsung(session: Session) -> Ticker:
    repo = TickerRepository(session)
    t = repo.save(Ticker(
        ticker="005930", name="삼성전자",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    StockDailyCandleRepository(session).bulk_upsert([
        StockDailyCandle(ticker_id=t.id, date=date(2024, 1, 2), open=70000, high=71000,
                          low=69500, close=70500, volume=12_000_000, trade_value=None),
        StockDailyCandle(ticker_id=t.id, date=date(2024, 1, 3), open=70500, high=72000,
                          low=70000, close=71800, volume=15_000_000, trade_value=None),
    ])
    return t


def _service(session: Session, client: MagicMock) -> AdjustedCandleBackfillService:
    return AdjustedCandleBackfillService(
        client=client,
        ticker_repository=TickerRepository(session),
        daily_candle_repository=StockDailyCandleRepository(session),
    )


def test_백필_기존row_adj컬럼_갱신(session: Session, samsung: Ticker) -> None:
    """네이버 수정주가를 기존 일봉 날짜와 매칭해 adj_*를 채운다."""
    client = MagicMock(spec=PykrxDailyCandleClient)
    client.fetch_adjusted_by_ticker.return_value = [
        PykrxAdjustedCandle(date=date(2024, 1, 2), open=1400, high=1420, low=1390, close=1410, volume=600_000_000),
        PykrxAdjustedCandle(date=date(2024, 1, 3), open=1410, high=1440, low=1400, close=1436, volume=750_000_000),
    ]
    service = _service(session, client)

    result = service.backfill("005930")

    assert result.fetched == 2
    assert result.updated == 2
    # 조회 범위는 기존 row의 min~max
    client.fetch_adjusted_by_ticker.assert_called_once_with("005930", date(2024, 1, 2), date(2024, 1, 3))
    rows = StockDailyCandleRepository(session).find_by_ticker(samsung.id)
    assert rows[0].adj_close == 1410
    assert rows[0].adj_volume == 600_000_000
    assert rows[0].close == 70500  # 원주가 보존


def test_백필_미매칭_날짜_무시(session: Session, samsung: Ticker) -> None:
    """DB에 없는 날짜의 수정주가는 갱신하지 않는다."""
    client = MagicMock(spec=PykrxDailyCandleClient)
    client.fetch_adjusted_by_ticker.return_value = [
        PykrxAdjustedCandle(date=date(2024, 1, 2), open=1400, high=1420, low=1390, close=1410, volume=600_000_000),
        PykrxAdjustedCandle(date=date(2024, 1, 4), open=1, high=1, low=1, close=1, volume=1),  # 미존재
    ]
    service = _service(session, client)

    result = service.backfill("005930")

    assert result.fetched == 2
    assert result.updated == 1


def test_백필_미발견_ticker_404(session: Session) -> None:
    client = MagicMock(spec=PykrxDailyCandleClient)
    service = _service(session, client)
    with pytest.raises(GenieError):
        service.backfill("999999")


def test_백필_원주가_row없으면_스킵(session: Session) -> None:
    """원주가 row가 없으면 외부 호출 없이 0건 반환."""
    repo = TickerRepository(session)
    repo.save(Ticker(
        ticker="000660", name="SK하이닉스",
        asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
    ))
    client = MagicMock(spec=PykrxDailyCandleClient)
    service = _service(session, client)

    result = service.backfill("000660")

    assert result.fetched == 0
    assert result.updated == 0
    client.fetch_adjusted_by_ticker.assert_not_called()
