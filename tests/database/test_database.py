"""Tests for Database class."""

from sqlalchemy.orm import Session

from src.database.database import Database


def test_database_create_tables(db: Database) -> None:
    """테이블 생성 테스트"""
    # Given - db fixture에서 이미 테이블 생성됨

    # When - 테이블이 존재하는지 확인
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    # Then
    assert "candle_minute_1" in tables
    assert "candle_daily" in tables


def test_database_get_session(db: Database) -> None:
    """세션 생성 테스트"""
    # When
    session = db.get_session()

    # Then
    assert isinstance(session, Session)
    assert session.is_active

    # 정리
    session.close()


def test_database_session_isolation(db: Database) -> None:
    """세션 격리 테스트"""
    # When - 두 개의 세션 생성
    session1 = db.get_session()
    session2 = db.get_session()

    # Then - 서로 다른 세션
    assert session1 is not session2

    # 정리
    session1.close()
    session2.close()
