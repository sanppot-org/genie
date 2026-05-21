"""스케줄러 task DB 세션 스코프 데코레이터 검증.

HTTP `test_session_scope.py`와 대칭. `@db_scoped`가 task 단위로 scoped_session을
열고 닫는지 — 같은 task 내 리포가 동일 Session 공유, 정상/예외 모두 close,
다음 task로 누수 0 — 회귀 감지.
"""

from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import container
from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database, make_request_session
from src.database.models import Base, Ticker
from src.database.request_scope import current_request_token
from src.database.ticker_repository import TickerRepository
from src.scheduled_tasks.scope import configure_db_scoped, db_scoped, mark_rollback_only


def _make_database() -> Database:
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


@pytest.fixture
def tracked_db() -> Generator[tuple[Database, list[Session]], Any, None]:
    """세션 close 호출을 추적하는 Database (container.database override)."""
    db = _make_database()
    created: list[Session] = []
    real_factory = db.SessionLocal

    def tracking_factory() -> Session:
        sess = real_factory()
        flag = {"closed": False}
        original_close = sess.close

        def close_spy() -> None:
            flag["closed"] = True
            original_close()

        sess.close = close_spy  # type: ignore[method-assign]
        sess.leak_flag = flag  # type: ignore[attr-defined]
        created.append(sess)
        return sess

    db.SessionLocal = tracking_factory  # type: ignore[assignment]
    db.RequestSession = make_request_session(tracking_factory)  # type: ignore[arg-type]

    container.database.override(db)
    configure_db_scoped(container.database)
    yield db, created
    container.database.reset_override()
    db.engine.dispose()


def test_정상_종료시_세션_close(tracked_db: tuple[Database, list[Session]]) -> None:
    db, created = tracked_db

    @db_scoped
    def task() -> None:
        TickerRepository(db.RequestSession()).find_all()

    task()

    assert len(created) == 1, "task당 세션 1개 기대"
    assert created[0].leak_flag["closed"], "정상 종료 시 close 누락 = 커넥션 누수"
    assert current_request_token() is None, "스코프 토큰 해제 누락"


def test_예외_발생시에도_세션_close(tracked_db: tuple[Database, list[Session]]) -> None:
    db, created = tracked_db

    @db_scoped
    def task() -> None:
        TickerRepository(db.RequestSession()).find_all()
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        task()

    assert len(created) == 1
    assert created[0].leak_flag["closed"], "예외 경로 close 누락 = idle-in-transaction 잔존"
    assert current_request_token() is None


def test_같은_task_내_여러_리포가_세션_공유(tracked_db: tuple[Database, list[Session]]) -> None:
    """scopefunc=토큰 기준으로 task 내 모든 RequestSession() 호출이 같은 인스턴스를 반환."""
    db, created = tracked_db

    @db_scoped
    def task() -> None:
        # 같은 task에서 여러 리포가 세션을 받아도 1개만 생성돼야 함
        s1 = db.RequestSession()
        s2 = db.RequestSession()
        assert s1 is s2, "scoped_session이 같은 task 안에서 동일 인스턴스를 줘야 함"

    task()
    assert len(created) == 1, f"task당 세션 1개 기대, 실제 {len(created)}개"


def test_중첩_호출시_outer가_라이프사이클_소유(tracked_db: tuple[Database, list[Session]]) -> None:
    """중첩 @db_scoped는 reentrancy 가드로 outer scope 공유 — 세션 1개, 1회 close.

    가드 없이는 inner가 토큰을 덮어쓰고 None으로 클리어 → outer 세션 누수 +
    outer post-inner DB 호출이 레거시 폴백으로 빠짐. 회귀 감지.
    """
    db, created = tracked_db

    @db_scoped
    def inner() -> None:
        TickerRepository(db.RequestSession()).find_all()

    @db_scoped
    def outer() -> None:
        s_before = db.RequestSession()
        TickerRepository(s_before).find_all()
        inner()
        s_after = db.RequestSession()
        assert s_after is s_before, "중첩 후에도 outer 세션 유지 — 토큰 보존 실패"

    outer()
    assert len(created) == 1, f"중첩 호출도 세션 1개 기대, 실제 {len(created)}개"
    assert created[0].leak_flag["closed"], "outer 종료 시 close 누락 = 누수"
    assert current_request_token() is None


def _make_ticker(code: str) -> Ticker:
    return Ticker(ticker=code, asset_type=AssetType.KR_STOCK, data_source=DataSource.PYKRX.value)


def test_정상_종료시_boundary가_미커밋_쓰기를_commit(tracked_db: tuple[Database, list[Session]]) -> None:
    """task 본문은 flush만 하고, 데코레이터가 task 단위 commit을 책임진다."""
    db, _ = tracked_db

    @db_scoped
    def task() -> None:
        TickerRepository(db.RequestSession()).save(_make_ticker("AAA"))

    task()

    verify = db.SessionLocal()
    try:
        assert verify.query(Ticker).filter_by(ticker="AAA").count() == 1, "boundary commit 누락"
    finally:
        verify.close()


def test_예외_발생시_multi_write가_모두_rollback(tracked_db: tuple[Database, list[Session]]) -> None:
    """service가 여러 write를 조합하다가 뒤에서 실패하면 앞선 변경도 rollback.

    기존엔 repo가 즉시 commit해서 silent partial commit이 가능했다.
    boundary commit + flush-only repo로 멀티-write atomicity 보장.
    """
    db, _ = tracked_db

    @db_scoped
    def task() -> None:
        repo = TickerRepository(db.RequestSession())
        repo.save(_make_ticker("AAA"))
        repo.save(_make_ticker("BBB"))
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        task()

    verify = db.SessionLocal()
    try:
        assert verify.query(Ticker).count() == 0, "예외 경로 rollback 실패 = silent partial commit"
    finally:
        verify.close()


def test_mark_rollback_only_시_swallow된_예외에도_partial_flush_rollback(
    tracked_db: tuple[Database, list[Session]],
) -> None:
    """task가 예외를 catch + mark_rollback_only → flush된 write 폐기."""
    db, _ = tracked_db

    @db_scoped
    def task() -> None:
        TickerRepository(db.RequestSession()).save(_make_ticker("AAA"))
        try:
            raise RuntimeError("inner")
        except RuntimeError:
            mark_rollback_only()

    task()  # 정상 return

    verify = db.SessionLocal()
    try:
        assert verify.query(Ticker).count() == 0, (
            "mark_rollback_only 무시 = silent partial commit (F3 회귀)"
        )
    finally:
        verify.close()


def test_연속_task_사이에_rollback_flag_누출되지_않는다(
    tracked_db: tuple[Database, list[Session]],
) -> None:
    """앞 task에서 mark_rollback_only 호출 후, 다음 task는 정상 commit 동작."""
    db, _ = tracked_db

    @db_scoped
    def task_rollback() -> None:
        TickerRepository(db.RequestSession()).save(_make_ticker("AAA"))
        mark_rollback_only()

    @db_scoped
    def task_normal() -> None:
        TickerRepository(db.RequestSession()).save(_make_ticker("BBB"))

    task_rollback()
    task_normal()

    verify = db.SessionLocal()
    try:
        rows = {t.ticker for t in verify.query(Ticker).all()}
        assert rows == {"BBB"}, f"플래그 누출 또는 commit 누락: {rows}"
    finally:
        verify.close()


def test_연속_task_세션_누수_0(tracked_db: tuple[Database, list[Session]]) -> None:
    """task를 반복 실행해도 이전 세션이 닫히고 새 세션이 생성된다(누수 0)."""
    db, created = tracked_db

    @db_scoped
    def task() -> None:
        TickerRepository(db.RequestSession()).find_all()

    for _ in range(20):
        task()

    assert len(created) == 20, f"task당 세션 1개 × 20회 기대, 실제 {len(created)}"
    assert all(s.leak_flag["closed"] for s in created), "닫히지 않은 세션 = 누수"
