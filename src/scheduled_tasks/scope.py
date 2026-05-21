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
from contextvars import ContextVar
from functools import wraps

from src.database.database import Database
from src.database.request_scope import begin_scope, current_request_token, end_scope

_database_provider: Callable[[], Database] | None = None

_rollback_flag: ContextVar[bool] = ContextVar("genie_db_scope_rollback", default=False)


def configure_db_scoped(database_provider: Callable[[], Database]) -> None:
    """앱 부팅 시 1회 호출: 데코레이터가 사용할 Database provider 등록."""
    global _database_provider
    _database_provider = database_provider


def mark_rollback_only() -> None:
    """현재 task scope의 트랜잭션을 commit하지 말고 rollback하라고 표시.

    task가 예외를 catch해서 정상 return하지만 부분 flush를 폐기해야 할 때 호출.
    `except Exception: ... slack.send(...)` 같은 swallowing 패턴에서 silent
    partial commit을 방지한다.
    """
    _rollback_flag.set(True)


def db_scoped[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """스케줄러 task 진입에서 scope 시작, 종료 시 scoped_session 정리.

    DB 미사용 task에도 안전(`RequestSession.remove()`는 세션 미체크아웃 시 no-op).
    `@inject`보다 바깥에 둔다 → wrapper가 scope를 열고 `@inject`가 의존성 주입.

    Reentrant: 이미 outer scope(HTTP 미들웨어 또는 다른 `@db_scoped`) 안이면
    그대로 위임 → 세션/토큰을 outer와 공유, inner는 라이프사이클 미관여.

    Boundary unit-of-work: 정상 종료 시 commit, 예외 시 close()가 자동 rollback.
    task가 예외를 catch해서 정상 return하지만 부분 변경을 폐기하고 싶으면
    `mark_rollback_only()` 호출.
    """

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if _database_provider is None:
            raise RuntimeError(
                "db_scoped not configured — app.py에서 configure_db_scoped(container.database) 호출 필요",
            )
        if current_request_token() is not None:
            return fn(*args, **kwargs)
        db = _database_provider()
        begin_scope()
        _rollback_flag.set(False)
        try:
            result = fn(*args, **kwargs)
            # 정상 종료 — task 단위 unit-of-work commit (HTTP 미들웨어와 대칭).
            # DB 미사용 task는 registry.has() False라 건너뛴다.
            # `mark_rollback_only()`로 명시된 경우 commit 대신 rollback (예외
            # swallowing 패턴에서 partial flush 폐기).
            if db.RequestSession.registry.has():
                sess = db.RequestSession()
                if sess.in_transaction():
                    if _rollback_flag.get():
                        sess.rollback()
                    else:
                        sess.commit()
            return result
        finally:
            # 예외 경로는 commit/rollback 분기를 거치지 않고 여기로 옴 → remove()의
            # close()가 미커밋 트랜잭션 자동 rollback. 플래그도 다음 task를 위해 초기화.
            _rollback_flag.set(False)
            db.RequestSession.remove()
            end_scope()

    return wrapper
