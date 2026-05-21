"""요청 스코프 DB 세션 ASGI 미들웨어."""

from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from src.database.database import Database
from src.database.request_scope import begin_scope, end_scope


class DBSessionMiddleware:
    """HTTP 요청마다 요청 스코프 토큰을 설정하고, 응답 후 scoped_session을 정리.

    SQLAlchemy 공식 scoped_session 패턴: scopefunc=`current_request_token`이라
    같은 요청의 모든 리포지토리가 `db.RequestSession()`으로 동일 Session을
    공유(명시적 전달 없이)하고, 요청 끝에 `.remove()`(close+rollback+폐기)로
    커넥션을 반환 → 누수 차단.

    pure ASGI 미들웨어라 다운스트림과 동일 태스크/컨텍스트에서 실행 → 여기서
    설정한 토큰 ContextVar가 동기 엔드포인트의 threadpool 컨텍스트 복사에
    포함된다. `BaseHTTPMiddleware`는 자식 태스크라 contextvar가 전파되지 않아
    사용하지 않는다. 스케줄러 task 경로는 `src.scheduled_tasks.scope.db_scoped`
    데코레이터가 동일 메커니즘으로 처리한다.
    """

    def __init__(self, app: ASGIApp, database_provider: Callable[[], Database]) -> None:
        self.app = app
        self._database = database_provider

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        begin_scope()
        try:
            await self.app(scope, receive, send)
        finally:
            # token이 아직 설정된 상태에서 remove() → scopefunc로 현재 요청의
            # 세션을 찾아 close+rollback+폐기. DB 미사용 요청은 no-op.
            self._database().RequestSession.remove()
            end_scope()
