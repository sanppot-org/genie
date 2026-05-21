"""DB 세션 누수 Phase 1 핫픽스 검증.

- session_scope: 정상 시 commit·항상 close, 예외 시 rollback·close
- HTTP read 경로: 요청당 세션 1개를 리포가 공유하고 항상 닫힘(누수 0),
  예외(404) 경로도 close (Starlette 제너레이터 teardown 확인)
"""

from collections.abc import Generator
from datetime import date
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app import app, container
from src.api.middleware import DBSessionMiddleware
from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database, make_request_session
from src.database.models import Base, StockDailyCandle, Ticker
from src.database.ticker_repository import TickerRepository
from src.service.exceptions import GenieError


def _make_database() -> Database:
    # StaticPool + check_same_thread=False: 단일 공유 커넥션 → TestClient
    # 워커 스레드에서도 시드 데이터 가시(인메모리 sqlite 스레드 분리 회피).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    db = Database.__new__(Database)
    db.engine = engine
    db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.RequestSession = make_request_session(db.SessionLocal)
    Base.metadata.create_all(bind=engine)
    return db


def test_session_scope_정상시_commit_후_close() -> None:
    db = Database.__new__(Database)
    fake = MagicMock()
    fake.in_transaction.return_value = True
    db.SessionLocal = MagicMock(return_value=fake)

    with db.session_scope() as s:
        assert s is fake

    fake.commit.assert_called_once()
    fake.close.assert_called_once()
    fake.rollback.assert_not_called()


def test_session_scope_예외시_rollback_후_close() -> None:
    db = Database.__new__(Database)
    fake = MagicMock()
    fake.in_transaction.return_value = True
    db.SessionLocal = MagicMock(return_value=fake)

    with pytest.raises(RuntimeError), db.session_scope():
        raise RuntimeError("boom")

    fake.rollback.assert_called_once()
    fake.close.assert_called_once()
    fake.commit.assert_not_called()


@pytest.fixture
def seeded_db() -> Generator[Database, Any, None]:
    """삼성전자 + 일봉 2건이 시드된 sqlite Database (container.database override)."""
    db = _make_database()
    s = db.get_session()
    ticker = Ticker(
        ticker="005930",
        name="삼성전자",
        asset_type=AssetType.KR_STOCK,
        data_source=DataSource.PYKRX,
    )
    s.add(ticker)
    s.flush()
    s.add_all(
        [
            StockDailyCandle(
                ticker_id=ticker.id, date=date(2026, 5, 15),
                open=70000, high=71000, low=69500, close=70500, volume=100, trade_value=7_000_000,
            ),
            StockDailyCandle(
                ticker_id=ticker.id, date=date(2026, 5, 16),
                open=70500, high=72000, low=70000, close=71800, volume=120, trade_value=8_500_000,
            ),
        ]
    )
    s.commit()
    s.close()

    container.database.override(db)
    yield db
    container.database.reset_override()
    db.engine.dispose()


def _make_test_app() -> FastAPI:
    """미들웨어만 장착한 최소 FastAPI 앱 — boundary commit 단위 테스트용."""
    test_app = FastAPI()

    async def _handle_genie(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, GenieError)
        return exc.to_json_response()

    test_app.add_exception_handler(GenieError, _handle_genie)
    test_app.add_middleware(DBSessionMiddleware, database_provider=container.database)
    return test_app


def test_4xx_응답시_partial_flush_rollback(seeded_db: Database) -> None:
    """endpoint가 save 후 GenieError raise → 핸들러가 409 변환 → middleware rollback.

    repo는 flush만 하므로 middleware가 status<400만 commit해야 한다.
    안 그러면 클라이언트는 409를 받았는데 DB엔 save된 row가 남는 정합성 깨짐.
    """
    test_app = _make_test_app()

    @test_app.get("/save-then-conflict")
    def save_then_conflict() -> None:
        TickerRepository(seeded_db.RequestSession()).save(
            Ticker(ticker="ZZZ", asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX),
        )
        raise GenieError.already_exists(name="ZZZ")

    r = TestClient(test_app).get("/save-then-conflict")
    assert r.status_code == 409, r.text

    verify = seeded_db.SessionLocal()
    try:
        assert verify.query(Ticker).filter_by(ticker="ZZZ").count() == 0, (
            "4xx 응답인데 partial flush가 commit됨 (F2 회귀)"
        )
    finally:
        verify.close()


def test_2xx_응답시_write_commit(seeded_db: Database) -> None:
    """endpoint가 save 후 정상 응답 → middleware가 unit-of-work commit."""
    test_app = _make_test_app()

    @test_app.get("/save-ok")
    def save_ok() -> dict[str, bool]:
        TickerRepository(seeded_db.RequestSession()).save(
            Ticker(ticker="WWW", asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX),
        )
        return {"ok": True}

    r = TestClient(test_app).get("/save-ok")
    assert r.status_code == 200, r.text

    verify = seeded_db.SessionLocal()
    try:
        assert verify.query(Ticker).filter_by(ticker="WWW").count() == 1, "2xx commit 누락"
    finally:
        verify.close()


def test_commit_실패시_500으로_대체되고_rollback(seeded_db: Database) -> None:
    """commit이 실패하면 클라이언트가 2xx 받지 않고 500을 받아야 한다.

    응답 send는 commit 성공 후로 버퍼링되므로, commit 예외 시 미들웨어가 500을
    직접 송신한다. 동시에 close()가 rollback해서 partial write가 남지 않는다.
    """
    test_app = _make_test_app()

    @test_app.get("/save-then-commit-fails")
    def save_then_commit_fails() -> dict[str, bool]:
        TickerRepository(seeded_db.RequestSession()).save(
            Ticker(ticker="VVV", asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX),
        )
        return {"ok": True}

    real_factory = seeded_db.SessionLocal

    def failing_factory() -> Session:
        sess = real_factory()
        sess.commit = MagicMock(side_effect=RuntimeError("simulated commit failure"))  # type: ignore[method-assign]
        return sess

    original_request_session = seeded_db.RequestSession
    seeded_db.RequestSession = make_request_session(failing_factory)  # type: ignore[arg-type]
    try:
        r = TestClient(test_app).get("/save-then-commit-fails")
        assert r.status_code == 500, f"commit 실패 → 500 변환 누락 (got {r.status_code})"
    finally:
        seeded_db.RequestSession = original_request_session

    verify = real_factory()
    try:
        assert verify.query(Ticker).filter_by(ticker="VVV").count() == 0, "commit 실패 후 rollback 누락"
    finally:
        verify.close()


def test_read_요청_반복시_세션_누수_없음(seeded_db: Database) -> None:
    """요청마다 세션 1개를 ticker/candle 리포가 공유하고 모두 닫힌다.

    토큰 전파가 깨지면 리포가 레거시 폴백(get_session)으로 별도 세션을 추가
    생성하고 닫지 않으므로 두 단언 모두 실패한다 → 누수 회귀 감지.
    """
    created: list[Session] = []
    real_factory = seeded_db.SessionLocal

    def tracking_factory() -> Session:
        sess = real_factory()
        flag = {"closed": False}
        original_close = sess.close

        def close_spy() -> None:
            flag["closed"] = True
            original_close()

        sess.close = close_spy
        sess.leak_flag = flag  # type: ignore[attr-defined]
        created.append(sess)
        return sess

    # scoped_session은 생성 시점 factory를 캡처하므로 추적 팩토리로 재생성.
    seeded_db.SessionLocal = tracking_factory  # type: ignore[assignment]
    seeded_db.RequestSession = make_request_session(tracking_factory)  # type: ignore[arg-type]

    client = TestClient(app)
    for _ in range(40):
        r = client.get("/api/candles/kr-stock", params={"ticker": "005930"})
        assert r.status_code == 200, r.text
        assert len(r.json()["data"]["points"]) == 2

    # 예외(404) 경로도 미들웨어 finally의 RequestSession.remove()로 닫혀야 한다
    r = client.get("/api/candles/kr-stock", params={"ticker": "999999"})
    assert r.status_code == 404

    assert len(created) == 41, f"요청당 세션 1개(공유) 기대, 실제 {len(created)}개 — contextvar 전파 실패 의심"
    assert all(s.leak_flag["closed"] for s in created), "닫히지 않은 세션 존재 = 커넥션 누수"
