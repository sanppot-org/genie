"""TickerSyncService 통합 테스트 — 인메모리 SQLite + pykrx mock."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Base, Ticker
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_ticker_client import PykrxTickerClient, PykrxTickerInfo
from src.service.ticker_sync_service import SyncResult, TickerSyncService


@pytest.fixture
def test_session() -> Generator[Session, None, None]:
    """인메모리 SQLite 세션."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_pykrx_ticker(
    session: Session,
    ticker: str,
    name: str,
    *,
    active: bool,
    asset_type: AssetType = AssetType.KR_STOCK,
) -> None:
    """PYKRX 데이터소스 Ticker를 시드한다."""
    session.add(
        Ticker(
            ticker=ticker,
            name=name,
            asset_type=asset_type,
            data_source=DataSource.PYKRX.value,
            active=active,
        )
    )


def test_sync_handles_all_four_branches(test_session: Session) -> None:
    """신규/사라짐/이름변경/재상장 + 변동없음을 한 트랜잭션에서 처리한다."""
    # 시드: 5가지 케이스
    _seed_pykrx_ticker(test_session, "AAA", "에이", active=True)         # 변동 없음
    _seed_pykrx_ticker(test_session, "BBB", "비", active=True)           # 사라짐 → active=False
    _seed_pykrx_ticker(test_session, "CCC", "씨_옛이름", active=True)    # 이름 변경
    _seed_pykrx_ticker(test_session, "DDD", "디", active=False)          # 재상장 → active=True
    _seed_pykrx_ticker(test_session, "FFF", "에프", active=False)        # 이미 비활성 + 여전히 사라짐
    test_session.commit()

    # pykrx mock 결과 (BBB, FFF는 없음 — 상장 폐지된 상태)
    pykrx_results = [
        PykrxTickerInfo(ticker="AAA", name="에이", asset_type=AssetType.KR_STOCK),
        PykrxTickerInfo(ticker="CCC", name="씨_새이름", asset_type=AssetType.KR_STOCK),
        PykrxTickerInfo(ticker="DDD", name="디", asset_type=AssetType.KR_STOCK),
        PykrxTickerInfo(ticker="EEE", name="이", asset_type=AssetType.KR_ETF),  # 신규
    ]

    repo = TickerRepository(test_session)
    service = TickerSyncService(PykrxTickerClient(), repo)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        result = service.sync_pykrx()

    assert result == SyncResult(inserted=1, deactivated=1, renamed=1, reactivated=1, unchanged=2)

    # DB 직접 검증
    by_ticker = {t.ticker: t for t in test_session.query(Ticker).all()}
    assert by_ticker["AAA"].active is True
    assert by_ticker["AAA"].name == "에이"
    assert by_ticker["BBB"].active is False  # 사라짐
    assert by_ticker["CCC"].name == "씨_새이름"  # 이름 변경
    assert by_ticker["CCC"].active is True
    assert by_ticker["DDD"].active is True  # 재상장
    assert "EEE" in by_ticker  # 신규
    assert by_ticker["EEE"].name == "이"
    assert by_ticker["EEE"].asset_type == AssetType.KR_ETF
    assert by_ticker["EEE"].data_source == DataSource.PYKRX.value
    assert by_ticker["FFF"].active is False  # 이미 비활성, 변동 없음


def test_sync_inserts_all_when_db_empty(test_session: Session) -> None:
    """DB가 비어 있으면 pykrx 결과를 모두 신규 INSERT한다."""
    pykrx_results = [
        PykrxTickerInfo(ticker="AAA", name="에이", asset_type=AssetType.KR_STOCK),
        PykrxTickerInfo(ticker="BBB", name="비", asset_type=AssetType.KR_ETF),
    ]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session))

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        result = service.sync_pykrx()

    assert result == SyncResult(inserted=2, deactivated=0, renamed=0, reactivated=0, unchanged=0)
    assert test_session.query(Ticker).count() == 2

def test_sync_handles_rename_and_reactivate_on_same_row(test_session: Session) -> None:
    """이름 변경과 재상장이 같은 row에서 동시 발생 — renamed/reactivated 모두 +1."""
    _seed_pykrx_ticker(test_session, "AAA", "옛이름", active=False)
    test_session.commit()

    pykrx_results = [
        PykrxTickerInfo(ticker="AAA", name="새이름", asset_type=AssetType.KR_STOCK),
    ]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session))

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        result = service.sync_pykrx()

    assert result == SyncResult(inserted=0, deactivated=0, renamed=1, reactivated=1, unchanged=0)
    row = test_session.query(Ticker).filter_by(ticker="AAA").one()
    assert row.name == "새이름"
    assert row.active is True
