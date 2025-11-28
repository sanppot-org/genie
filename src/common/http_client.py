"""공통 HTTP 클라이언트 모듈

API 요청을 위한 재시도 로직이 포함된 HTTP 클라이언트 함수를 제공합니다.
"""

from enum import Enum

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class HTTPMethod(str, Enum):
    """HTTP 메서드"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def make_api_request(url: str, method: HTTPMethod = HTTPMethod.GET, **kwargs: object) -> requests.Response:  # type: ignore[no-any-unimported]
    """API 요청을 수행합니다. (재시도 로직 포함)

    네트워크 에러나 타임아웃 발생 시 최대 3회까지 재시도합니다.
    재시도 간격은 지수 백오프 방식으로 1초부터 시작하여 최대 4초까지 증가합니다.

    Args:
        method: HTTP 메서드 (HTTPMethod enum)
        url: 완전한 URL (예: "https://api.example.com/v1/endpoint")
        **kwargs: requests.request에 전달할 추가 인자 (headers, json, params 등)

    Returns:
        API 응답

    Raises:
        requests.ConnectionError: 네트워크 연결 실패 (3회 재시도 후)
        requests.Timeout: 요청 타임아웃 (3회 재시도 후)
    """
    return requests.request(method.value, url, **kwargs)  # type: ignore[arg-type]
