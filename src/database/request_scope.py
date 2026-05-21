"""DB 세션 스코프 토큰 (SQLAlchemy scoped_session scopefunc).

SQLAlchemy 공식 패턴(Contextual/Thread-local Sessions)에 따라
`scoped_session(SessionLocal, scopefunc=current_request_token)`의 scopefunc로
사용된다. 작업 단위(HTTP 요청 또는 스케줄러 task)마다 진입 지점에서 고유 토큰을
ContextVar에 설정하고 종료 시 해제하므로, 같은 단위의 모든 리포지토리가 동일
scopefunc 키 → 동일 Session을 공유한다(명시적 전달 없이). 토큰이 None이면
컨테이너가 레거시 `get_session()`으로 폴백한다(테스트/스크립트 직접 호출 등).

ContextVar는 실행 컨텍스트에 바인딩되며, 동기 엔드포인트가 anyio threadpool에서
실행돼도 컨텍스트가 워커 스레드로 복사되어 단위별로 격리된다.
"""

from contextvars import ContextVar

_request_token: ContextVar[object | None] = ContextVar("genie_request_token", default=None)


def current_request_token() -> object | None:
    """현재 스코프 토큰 (없으면 None). scoped_session scopefunc."""
    return _request_token.get()


def begin_scope() -> None:
    """스코프 시작: 고유 토큰 설정 (HTTP 미들웨어 / 스케줄러 task 데코레이터)."""
    _request_token.set(object())


def end_scope() -> None:
    """스코프 종료: 토큰 해제.

    `Token` 기반 `reset()`은 동기 미들웨어/엔드포인트가 서로 다른 threadpool
    컨텍스트일 때 "different Context"로 실패하므로 `set(None)`으로 해제한다.
    실행별 컨텍스트는 anyio가 호출마다 복사하므로 다음 작업으로 누출되지 않는다.
    """
    _request_token.set(None)
