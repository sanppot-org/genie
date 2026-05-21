"""스케줄러 task용 DB 세션 스코프 데코레이터.

HTTP 요청 경로의 `DBSessionMiddleware`와 대칭. task 진입에서 고유 토큰을
설정해 같은 task 내 모든 리포지토리가 동일 Session을 공유하고, 종료(정상·예외)
시 `RequestSession.remove()`로 close+rollback+폐기 → 커넥션 누수 및
idle-in-transaction 잔존 방지.

`configure_db_scoped(container.database)`로 부팅 시 1회 등록한 뒤
`@db_scoped` 데코레이터로 task를 감싼다. 미들웨어가 `database_provider`를
생성자 주입받는 것과 동일 패턴이다.
"""

from collections.abc import Callable
from functools import wraps

from src.database.database import Database
from src.database.request_scope import begin_scope, end_scope

_database_provider: Callable[[], Database] | None = None


def configure_db_scoped(database_provider: Callable[[], Database]) -> None:
    """앱 부팅 시 1회 호출: 데코레이터가 사용할 Database provider 등록."""
    global _database_provider
    _database_provider = database_provider


def db_scoped[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """스케줄러 task 진입에서 scope 시작, 종료 시 scoped_session 정리.

    DB 미사용 task에도 안전(`RequestSession.remove()`는 세션 미체크아웃 시 no-op).
    `@inject`보다 바깥에 둔다 → wrapper가 scope를 열고 `@inject`가 의존성 주입.
    """

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if _database_provider is None:
            raise RuntimeError(
                "db_scoped not configured — app.py에서 configure_db_scoped(container.database) 호출 필요",
            )
        begin_scope()
        try:
            return fn(*args, **kwargs)
        finally:
            _database_provider().RequestSession.remove()
            end_scope()

    return wrapper
