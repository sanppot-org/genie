"""Tests for AdjustedCandleSyncService (단건 + 전종목 배치)."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import StockDailyCandle, Ticker
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_daily_candle_client import PykrxAdjustedCandle, PykrxDailyCandleClient
from src.service.adjusted_candle_sync_service import AdjustedCandleSyncService
from src.service.exceptions import GenieError


def _seed(db: Database) -> None:
    """005930(2건) + 000660(1건) 시드 후 커밋."""
    session = db.get_session()
    try:
        tr = TickerRepository(session)
        sam = tr.save(Ticker(ticker="005930", name="삼성전자",
                             asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
        sk = tr.save(Ticker(ticker="000660", name="SK하이닉스",
                            asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
        cr = StockDailyCandleRepository(session)
        cr.bulk_upsert([
            StockDailyCandle(ticker_id=sam.id, date=date(2024, 1, 2), open=70000, high=71000,
                             low=69500, close=70500, volume=12_000_000, trade_value=None),
            StockDailyCandle(ticker_id=sam.id, date=date(2024, 1, 3), open=70500, high=72000,
                             low=70000, close=71800, volume=15_000_000, trade_value=None),
            StockDailyCandle(ticker_id=sk.id, date=date(2024, 1, 2), open=130000, high=131000,
                             low=129000, close=130500, volume=3_000_000, trade_value=None),
        ])
        session.commit()
    finally:
        session.close()


def _adj(code: str, frm: date, to: date) -> list[PykrxAdjustedCandle]:
    """ticker별 네이버 수정주가 모킹."""
    if code == "005930":
        return [
            PykrxAdjustedCandle(date=date(2024, 1, 2), open=1400, high=1420, low=1390, close=1410, volume=600_000_000),
            PykrxAdjustedCandle(date=date(2024, 1, 3), open=1410, high=1440, low=1400, close=1436, volume=750_000_000),
        ]
    if code == "000660":
        return [
            PykrxAdjustedCandle(date=date(2024, 1, 2), open=2600, high=2620, low=2580, close=2610, volume=150_000_000),
        ]
    return []


@pytest.fixture
def client() -> MagicMock:
    m = MagicMock(spec=PykrxDailyCandleClient)
    m.fetch_adjusted_by_ticker.side_effect = _adj
    return m


def _adj_close(db: Database, ticker: str, d: date) -> float | None:
    session = db.get_session()
    try:
        tid = TickerRepository(session).find_by_ticker(ticker).id
        rows = StockDailyCandleRepository(session).find_by_ticker(tid)
        return next((r.adj_close for r in rows if r.date == d), None)
    finally:
        session.close()


class TestBackfillOne:
    def test_단건_백필_adj_갱신(self, db: Database, client: MagicMock) -> None:
        _seed(db)
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)

        result = service.backfill_one("005930", now=date(2024, 1, 3))

        assert result.fetched == 2
        assert result.updated == 2
        assert result.existing == 2
        assert result.partial is False
        assert _adj_close(db, "005930", date(2024, 1, 2)) == 1410

    def test_부분_보정_partial_플래그(self, db: Database) -> None:
        """네이버가 기존 row 일부만 커버하면 partial=True."""
        _seed(db)
        client = MagicMock(spec=PykrxDailyCandleClient)
        client.fetch_adjusted_by_ticker.return_value = [
            PykrxAdjustedCandle(date=date(2024, 1, 2), open=1400, high=1420, low=1390, close=1410, volume=600_000_000),
        ]  # 1/3 누락 → existing=2, updated=1
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)

        result = service.backfill_one("005930", now=date(2024, 1, 3))

        assert result.existing == 2
        assert result.updated == 1
        assert result.partial is True

    def test_미발견_ticker_404(self, db: Database, client: MagicMock) -> None:
        _seed(db)
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)
        with pytest.raises(GenieError):
            service.backfill_one("999999")


class TestSyncAll:
    def test_전종목_백필(self, db: Database, client: MagicMock) -> None:
        _seed(db)
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)

        result = service.sync(now=date(2024, 1, 3))

        assert result.ticker_count == 2
        assert result.api_attempted == 2
        assert result.api_failed == 0
        assert result.tickers_updated == 2
        assert result.rows_updated == 3  # 005930 2건 + 000660 1건
        assert _adj_close(db, "005930", date(2024, 1, 3)) == 1436
        assert _adj_close(db, "000660", date(2024, 1, 2)) == 2610

    def test_only_stale_이미_백필_종목_skip(self, db: Database, client: MagicMock) -> None:
        _seed(db)
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)
        # 005930만 먼저 백필
        service.backfill_one("005930", now=date(2024, 1, 3))
        client.fetch_adjusted_by_ticker.reset_mock()

        result = service.sync(only_stale=True, now=date(2024, 1, 3))

        assert result.skipped_already == 1               # 005930 skip
        assert result.api_attempted == 1                 # 000660만
        # 005930은 재호출 안 됨
        called = [c.args[0] for c in client.fetch_adjusted_by_ticker.call_args_list]
        assert "005930" not in called
        assert "000660" in called

    def test_ticker_codes_지정(self, db: Database, client: MagicMock) -> None:
        _seed(db)
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)

        result = service.sync(ticker_codes=["000660"], now=date(2024, 1, 3))

        assert result.ticker_count == 1
        assert result.tickers_updated == 1

    def test_종목_실패_격리(self, db: Database) -> None:
        """한 종목 네이버 호출 실패해도 다른 종목은 처리되고 실패는 집계."""
        _seed(db)
        client = MagicMock(spec=PykrxDailyCandleClient)

        def _side(code: str, frm: date, to: date) -> list[PykrxAdjustedCandle]:
            if code == "005930":
                raise RuntimeError("naver blocked")
            return _adj(code, frm, to)

        client.fetch_adjusted_by_ticker.side_effect = _side
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)

        result = service.sync(now=date(2024, 1, 3))

        assert result.api_failed == 1
        assert result.failed_tickers == ["005930"]
        assert result.tickers_updated == 1               # 000660 정상


def _seed_split(db: Database) -> None:
    """005930에 분할(종가 70000→1400, ratio 0.02) + 000660 정상."""
    session = db.get_session()
    try:
        tr = TickerRepository(session)
        sam = tr.save(Ticker(ticker="005930", name="삼성전자",
                             asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
        sk = tr.save(Ticker(ticker="000660", name="SK하이닉스",
                            asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value))
        cr = StockDailyCandleRepository(session)
        cr.bulk_upsert([
            StockDailyCandle(ticker_id=sam.id, date=date(2024, 1, 2), open=70000, high=71000,
                             low=69500, close=70000, volume=12_000_000, trade_value=None),
            StockDailyCandle(ticker_id=sam.id, date=date(2024, 1, 3), open=1400, high=1430,
                             low=1390, close=1400, volume=600_000_000, trade_value=None),  # 분할
            StockDailyCandle(ticker_id=sk.id, date=date(2024, 1, 2), open=130000, high=131000,
                             low=129000, close=130000, volume=3_000_000, trade_value=None),
            StockDailyCandle(ticker_id=sk.id, date=date(2024, 1, 3), open=130500, high=132000,
                             low=130000, close=131000, volume=3_500_000, trade_value=None),  # 정상
        ])
        session.commit()
    finally:
        session.close()


class TestSplitDetection:
    def test_분할_종목만_감지(self, db: Database) -> None:
        _seed_split(db)
        session = db.get_session()
        try:
            repo = StockDailyCandleRepository(session)
            sam_id = TickerRepository(session).find_by_ticker("005930").id
            sk_id = TickerRepository(session).find_by_ticker("000660").id

            ids = repo.find_split_candidate_ticker_ids(date(2024, 1, 3))

            assert sam_id in ids        # 분할(0.02)
            assert sk_id not in ids      # 정상(1.008)
        finally:
            session.close()

    def test_since_이전_급변_제외(self, db: Database) -> None:
        """분할일이 since 이전이면 후보에서 제외."""
        _seed_split(db)
        session = db.get_session()
        try:
            repo = StockDailyCandleRepository(session)
            ids = repo.find_split_candidate_ticker_ids(date(2024, 1, 4))  # 01-03 분할 < since
            assert ids == set()
        finally:
            session.close()

    def test_장기_거래정지_후_재개_감자_감지(self, db: Database) -> None:
        """정지 이전 행이 스캔 윈도우 밖이어도 감지한다 (거리 무관 직전 종가 비교).

        prod 실제 사례: 미래산업 025560이 21일 거래정지 후 1:5 감자로 재개됐으나
        LAG 기반 20일 윈도우로는 직전 종가가 NULL이 되어 조용히 누락됐다.
        """
        session = db.get_session()
        try:
            t = TickerRepository(session).save(Ticker(
                ticker="025560", name="미래산업",
                asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
            ))
            StockDailyCandleRepository(session).bulk_upsert([
                # 정지 이전 (재개일로부터 60일 전 — 어떤 고정 버퍼로도 못 덮는 거리)
                StockDailyCandle(ticker_id=t.id, date=date(2024, 1, 2), open=41000, high=42000,
                                 low=40500, close=41750, volume=100_000, trade_value=None),
                # 21일 넘는 공백 후 재개 — 1:5 감자로 1/4 수준
                StockDailyCandle(ticker_id=t.id, date=date(2024, 3, 2), open=10000, high=10500,
                                 low=9900, close=10210, volume=500_000, trade_value=None),
            ])
            session.commit()
            ticker_id = t.id
        finally:
            session.close()

        session = db.get_session()
        try:
            ids = StockDailyCandleRepository(session).find_split_candidate_ticker_ids(date(2024, 3, 1))
            assert ticker_id in ids
        finally:
            session.close()

    def test_직전_종가가_없는_신규_상장은_제외(self, db: Database) -> None:
        """첫 거래일은 비교 대상이 없어 후보가 아니다 (상관 서브쿼리 NULL)."""
        session = db.get_session()
        try:
            t = TickerRepository(session).save(Ticker(
                ticker="900001", name="신규상장",
                asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value,
            ))
            StockDailyCandleRepository(session).bulk_upsert([
                StockDailyCandle(ticker_id=t.id, date=date(2024, 3, 2), open=10000, high=10500,
                                 low=9900, close=10210, volume=500_000, trade_value=None),
            ])
            session.commit()
        finally:
            session.close()

        session = db.get_session()
        try:
            ids = StockDailyCandleRepository(session).find_split_candidate_ticker_ids(date(2024, 3, 1))
            assert ids == set()
        finally:
            session.close()


class TestReadjustRecentSplits:
    def test_감지_종목_재백필(self, db: Database, client: MagicMock) -> None:
        _seed_split(db)
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)

        result = service.readjust_recent_splits(lookback_days=10, now=date(2024, 1, 3))

        assert result.api_attempted == 1                 # 005930만
        called = [c.args[0] for c in client.fetch_adjusted_by_ticker.call_args_list]
        assert called == ["005930"]
        assert _adj_close(db, "005930", date(2024, 1, 3)) == 1436

    def test_후보_없으면_noop(self, db: Database, client: MagicMock) -> None:
        _seed(db)  # 분할 없는 시드
        service = AdjustedCandleSyncService(db, client, throttle_sec=0)

        result = service.readjust_recent_splits(lookback_days=10, now=date(2024, 1, 3))

        assert result.api_attempted == 0
        client.fetch_adjusted_by_ticker.assert_not_called()
