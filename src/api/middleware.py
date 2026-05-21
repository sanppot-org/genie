"""요청 스코프 DB 세션 ASGI 미들웨어."""

from collections.abc import Callable
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.database.database import Database
from src.database.request_scope import begin_scope, end_scope

logger = logging.getLogger(__name__)

_INTERNAL_ERROR_HEADERS = [(b"content-type", b"application/json")]
_INTERNAL_ERROR_BODY = b'{"detail":"internal server error"}'


class DBSessionMiddleware:
    """HTTP 요청마다 요청 스코프 토큰을 설정하고, 응답 전송 전 commit/rollback.

    Unit-of-work boundary: repo는 flush만 하고 commit은 여기가 책임진다.

    - 응답 status < 400 → commit. commit 성공 후에만 클라이언트로 응답 전송
      (응답 send는 미들웨어가 버퍼링). commit 실패 시 500으로 대체해 클라이언트가
      "성공"을 받고 DB는 비어 있는 정합성 깨짐을 방지.
    - 응답 status >= 400 → rollback. 예외 핸들러가 4xx/5xx로 변환하면서 남긴
      partial flush를 폐기 (예: endpoint가 save 후 GenieError → 409 응답 시,
      save된 row를 commit하면 안 됨).
    - 미처리 예외 → close()의 자동 rollback + 500 응답 대체.

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
        db = self._database()
        buffered: list[Message] = []
        response_status = 500

        async def buffered_send(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = int(message["status"])
            buffered.append(message)

        fallback_to_500 = False
        try:
            await self.app(scope, receive, buffered_send)
            # 응답 status 기준 commit/rollback 결정. DB 미사용 요청은 registry
            # 미보유라 건너뜀.
            if db.RequestSession.registry.has():
                sess = db.RequestSession()
                if sess.in_transaction():
                    if response_status < 400:
                        try:
                            sess.commit()
                        except Exception:
                            logger.exception("DB commit 실패 → 500으로 대체")
                            fallback_to_500 = True
                    else:
                        sess.rollback()
        except Exception:
            logger.exception("미들웨어 처리 중 예외 → 500으로 대체")
            fallback_to_500 = True
        finally:
            # close()가 미커밋 트랜잭션 자동 rollback. 세션을 풀로 반환.
            db.RequestSession.remove()
            end_scope()

        if fallback_to_500:
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": _INTERNAL_ERROR_HEADERS,
            })
            await send({"type": "http.response.body", "body": _INTERNAL_ERROR_BODY})
        else:
            for message in buffered:
                await send(message)
