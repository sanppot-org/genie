"""TickerSyncService 통합 테스트 — 인메모리 SQLite + pykrx/DART mock."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Base, Ticker
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import DartCompanyClient, DartCompanyInfo
from src.providers.pykrx_ticker_client import EmptyPykrxResponseError, PykrxTickerClient, PykrxTickerInfo
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


@pytest.fixture
def noop_dart_client() -> MagicMock:
    """기본 DART mock — 모든 종목에 대해 None 반환 (메타데이터 미보강)."""
    client = MagicMock(spec=DartCompanyClient)
    client.fetch_company_info.return_value = None
    return client


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


def test_sync_handles_all_four_branches(test_session: Session, noop_dart_client: MagicMock) -> None:
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
    service = TickerSyncService(PykrxTickerClient(), repo, noop_dart_client)

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


def test_sync_inserts_all_when_db_empty(test_session: Session, noop_dart_client: MagicMock) -> None:
    """DB가 비어 있으면 pykrx 결과를 모두 신규 INSERT한다."""
    pykrx_results = [
        PykrxTickerInfo(ticker="AAA", name="에이", asset_type=AssetType.KR_STOCK),
        PykrxTickerInfo(ticker="BBB", name="비", asset_type=AssetType.KR_ETF),
    ]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), noop_dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        result = service.sync_pykrx()

    assert result == SyncResult(inserted=2, deactivated=0, renamed=0, reactivated=0, unchanged=0)
    assert test_session.query(Ticker).count() == 2


def test_sync_propagates_empty_pykrx_error_without_mutating_db(test_session: Session, noop_dart_client: MagicMock) -> None:
    """pykrx 빈 응답 시 client가 raise하는 EmptyPykrxResponseError는 service가 그대로 전파.
    DB의 기존 ticker는 deactivate되지 않는다 (mass deactivate 방지)."""
    _seed_pykrx_ticker(test_session, "AAA", "에이", active=True)
    _seed_pykrx_ticker(test_session, "BBB", "비", active=True)
    test_session.commit()

    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), noop_dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", side_effect=EmptyPykrxResponseError("boom")):
        with pytest.raises(EmptyPykrxResponseError):
            service.sync_pykrx()

    by_ticker = {t.ticker: t for t in test_session.query(Ticker).all()}
    assert by_ticker["AAA"].active is True
    assert by_ticker["BBB"].active is True


def test_sync_handles_rename_and_reactivate_on_same_row(test_session: Session, noop_dart_client: MagicMock) -> None:
    """이름 변경과 재상장이 같은 row에서 동시 발생 — renamed/reactivated 모두 +1."""
    _seed_pykrx_ticker(test_session, "AAA", "옛이름", active=False)
    test_session.commit()

    pykrx_results = [
        PykrxTickerInfo(ticker="AAA", name="새이름", asset_type=AssetType.KR_STOCK),
    ]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), noop_dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        result = service.sync_pykrx()

    assert result == SyncResult(inserted=0, deactivated=0, renamed=1, reactivated=1, unchanged=0)
    row = test_session.query(Ticker).filter_by(ticker="AAA").one()
    assert row.name == "새이름"
    assert row.active is True


def test_sync_enriches_inserted_tickers_with_dart_industry_code(test_session: Session) -> None:
    """신규 INSERT 시 DART에서 industry_code를 채운다."""
    dart_client = MagicMock(spec=DartCompanyClient)
    dart_client.fetch_company_info.side_effect = lambda code: DartCompanyInfo(
        stock_code=code, industry_code="26410"
    )

    pykrx_results = [PykrxTickerInfo(ticker="005930", name="삼성전자", asset_type=AssetType.KR_STOCK)]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        service.sync_pykrx()

    row = test_session.query(Ticker).filter_by(ticker="005930").one()
    assert row.industry_code == "26410"


def test_sync_backfills_industry_code_for_existing_rows_with_null(test_session: Session) -> None:
    """industry_code가 NULL인 기존 row는 다음 sync에서 자동 백필된다."""
    _seed_pykrx_ticker(test_session, "005930", "삼성전자", active=True)
    _seed_pykrx_ticker(test_session, "000660", "SK하이닉스", active=True)
    test_session.commit()

    dart_client = MagicMock(spec=DartCompanyClient)
    dart_client.fetch_company_info.side_effect = lambda code: DartCompanyInfo(
        stock_code=code, industry_code={"005930": "26410", "000660": "26110"}[code]
    )

    pykrx_results = [
        PykrxTickerInfo(ticker="005930", name="삼성전자", asset_type=AssetType.KR_STOCK),
        PykrxTickerInfo(ticker="000660", name="SK하이닉스", asset_type=AssetType.KR_STOCK),
    ]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        result = service.sync_pykrx()

    # 두 row 모두 industry_code가 채워짐 — pykrx 관점에서는 변동 없음(unchanged)
    assert result.unchanged == 2
    by_ticker = {t.ticker: t for t in test_session.query(Ticker).all()}
    assert by_ticker["005930"].industry_code == "26410"
    assert by_ticker["000660"].industry_code == "26110"
    assert dart_client.fetch_company_info.call_count == 2


def test_sync_does_not_recall_dart_for_rows_with_industry_code_already_set(test_session: Session) -> None:
    """industry_code가 이미 있는 row는 DART 재호출 없음 (idempotent)."""
    test_session.add(
        Ticker(
            ticker="005930",
            name="삼성전자",
            asset_type=AssetType.KR_STOCK,
            data_source=DataSource.PYKRX.value,
            active=True,
            industry_code="26410",
        )
    )
    test_session.commit()

    dart_client = MagicMock(spec=DartCompanyClient)
    pykrx_results = [PykrxTickerInfo(ticker="005930", name="삼성전자", asset_type=AssetType.KR_STOCK)]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        service.sync_pykrx()

    dart_client.fetch_company_info.assert_not_called()


def test_sync_does_not_call_dart_for_etf_tickers(test_session: Session) -> None:
    """ETF는 DART에 등록되지 않으므로 INSERT/백필 어느 분기에서도 호출되지 않는다."""
    _seed_pykrx_ticker(test_session, "069500", "KODEX 200", active=True, asset_type=AssetType.KR_ETF)
    test_session.commit()

    dart_client = MagicMock(spec=DartCompanyClient)

    pykrx_results = [
        PykrxTickerInfo(ticker="069500", name="KODEX 200", asset_type=AssetType.KR_ETF),
        PykrxTickerInfo(ticker="232080", name="TIGER 코스닥150", asset_type=AssetType.KR_ETF),  # 신규 ETF
    ]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        service.sync_pykrx()

    dart_client.fetch_company_info.assert_not_called()
    by_ticker = {t.ticker: t for t in test_session.query(Ticker).all()}
    assert by_ticker["069500"].industry_code is None
    assert by_ticker["232080"].industry_code is None


def test_sync_inserts_with_null_industry_when_dart_fails(test_session: Session) -> None:
    """DART 호출이 예외를 던지거나 None을 반환해도 sync는 진행되며 industry_code는 None."""
    dart_client = MagicMock(spec=DartCompanyClient)
    dart_client.fetch_company_info.side_effect = RuntimeError("DART 장애")

    pykrx_results = [PykrxTickerInfo(ticker="005930", name="삼성전자", asset_type=AssetType.KR_STOCK)]
    service = TickerSyncService(PykrxTickerClient(), TickerRepository(test_session), dart_client)

    with patch.object(PykrxTickerClient, "fetch_all", return_value=pykrx_results):
        result = service.sync_pykrx()

    assert result.inserted == 1
    row = test_session.query(Ticker).filter_by(ticker="005930").one()
    assert row.industry_code is None
