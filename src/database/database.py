"""Database connection and session management."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from src.config import DatabaseConfig
from src.database.models import Base
from src.database.request_scope import current_request_token


def make_request_session(session_factory: sessionmaker[Session]) -> scoped_session[Session]:
    """요청 스코프 세션 레지스트리 (SQLAlchemy 공식 scoped_session 패턴).

    scopefunc=`current_request_token` → 같은 요청의 모든 리포지토리가 동일
    Session 공유. 요청 끝에 미들웨어가 `.remove()`(close+rollback+폐기) 호출.
    """
    return scoped_session(session_factory, scopefunc=current_request_token)


class Database:
    """데이터베이스 연결 및 세션 관리 클래스

    SQLAlchemy를 사용하여 PostgreSQL/TimescaleDB에 연결하고 세션을 관리합니다.

    Attributes:
        config: 데이터베이스 설정
        engine: SQLAlchemy 엔진
        SessionLocal: 세션 팩토리
    """

    def __init__(self, config: DatabaseConfig) -> None:
        """데이터베이스 초기화

        Args:
            config: 데이터베이스 설정
        """
        self.config = config
        self.engine = create_engine(
            config.database_url,
            pool_size=10,  # 연결 풀 크기
            max_overflow=20,  # 최대 추가 연결 수
            pool_pre_ping=True,  # 연결 상태 확인
            pool_timeout=10,  # 풀 고갈 시 빠른 실패(진단 용이). 기본 30초.
            echo=False,  # SQL 로그 (개발시 True)
            connect_args={"options": "-c timezone=Asia/Seoul"},  # 세션 타임존 설정
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        # 요청 스코프 세션 레지스트리 (커넥션 누수 차단, Phase 1).
        self.RequestSession = make_request_session(self.SessionLocal)

    def create_tables(self) -> None:
        """모든 테이블 생성

        Base.metadata에 등록된 모든 테이블을 생성합니다.
        이미 존재하는 테이블은 무시됩니다.
        """
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self) -> None:
        """모든 테이블 삭제

        주의: 모든 데이터가 삭제됩니다!
        주로 테스트에서 사용됩니다.
        """
        Base.metadata.drop_all(bind=self.engine)

    def get_session(self) -> Session:
        """새 세션 생성

        Returns:
            SQLAlchemy 세션

        Example:
            >>> db = Database(config)
            >>> session = db.get_session()
            >>> try:
            >>>     # 데이터베이스 작업
            >>>     session.commit()
            >>> finally:
            >>>     session.close()
        """
        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """요청/작업 단위 세션 스코프.

        정상 종료 시 commit(읽기 전용이어도 트랜잭션을 닫아 Postgres
        idle-in-transaction 잔존 방지), 예외 시 rollback, 항상 close하여
        커넥션을 풀에 반환한다.

        Yields:
            SQLAlchemy 세션
        """
        session = self.SessionLocal()
        try:
            yield session
            if session.in_transaction():
                session.commit()
        except Exception:
            if session.in_transaction():
                session.rollback()
            raise
        finally:
            session.close()
