from datetime import datetime

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.common.slack.order_notification import OrderNotification
from src.config import SlackConfig
from src.constants import KST
from src.strategy.order.execution_result import ExecutionResult


class SlackClient:
    def __init__(self, config: SlackConfig) -> None:
        self.config = config

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
    )
    def _send_message(self, url: str, msg: str) -> None:
        now = datetime.now(KST)
        message = {"text": f"""[{now.strftime("%Y-%m-%d %H:%M:%S")}]\n{str(msg)}"""}
        requests.post(url, json=message, headers={"Content-Type": "application/json"})

    def send_report(self, msg: str) -> None:
        self._send_message(self.config.report_url, msg)

    def send_log(self, msg: str) -> None:
        self._send_message(self.config.log_url, msg)

    def send_debug(self, msg: str) -> None:
        self._send_message(self.config.debug_url, msg)

    def send_status(self, msg: str) -> None:
        self._send_message(self.config.status_url, msg)

    def send_order_notification(self, result: ExecutionResult) -> None:
        """
        주문 완료 시 Slack 알림 발송

        Args:
            result: 주문 결과
        """
        notification = OrderNotification.from_result(result)
        self.send_log(notification.to_message())
