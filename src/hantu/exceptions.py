import requests


class HantuConnectionError(requests.exceptions.RequestException):
    """KIS API 서버 연결 불가(점검/네트워크 장애 등 전송 계층 실패).

    requests.exceptions.RequestException 하위로 정의하여, 기존 KIS provider들의
    tenacity `retry_if_exception_type(requests.RequestException)` 및
    `except requests.RequestException` 블록과 완전 호환된다.
    """
