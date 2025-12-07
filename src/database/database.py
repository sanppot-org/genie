"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import DatabaseConfig
from src.database.models import Base


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
            echo=False,  # SQL 로그 (개발시 True)
            connect_args={"options": "-c timezone=Asia/Seoul"},  # 세션 타임존 설정
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

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
