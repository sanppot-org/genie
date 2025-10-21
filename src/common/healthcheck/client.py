import logging

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import HealthcheckConfig

logger = logging.getLogger(__name__)


class HealthcheckClient:
    """Healthchecks.io 클라이언트"""

    def __init__(self, config: HealthcheckConfig) -> None:
        self.config = config

    def is_enabled(self) -> bool:
        """헬스체크가 활성화되어 있는지 확인"""
        return self.config.healthcheck_url is not None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
    )
    def ping(self) -> None:
        """
        헬스체크 성공 신호 전송

        전략 실행이 성공적으로 완료되었을 때 호출합니다.
        """
        if not self.is_enabled():
            return

        try:
            requests.get(self.config.healthcheck_url, timeout=10)  # type: ignore
        except Exception as e:
            logger.error(f"Healthcheck ping 전송 실패: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
    )
    def ping_fail(self) -> None:
        """
        헬스체크 실패 신호 전송

        전략 실행이 실패했을 때 명시적으로 알리고 싶을 때 호출합니다.
        (선택사항: ping을 보내지 않으면 자동으로 타임아웃 감지됨)
        """
        if not self.is_enabled():
            return

        try:
            requests.get(f"{self.config.healthcheck_url}/fail", timeout=10)  # type: ignore
        except Exception as e:
            logger.error(f"Healthcheck fail 신호 전송 실패: {e}")
            raise
