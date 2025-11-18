import time
import uuid

import jwt
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.bithumb.model import BalanceInfo
from src.config import BithumbConfig


class BithumbApi:
    """빗썸 API 클라이언트"""

    API_BASE_URL = "https://api.bithumb.com"

    def __init__(self, config: BithumbConfig | None = None) -> None:
        if config is None:
            config = BithumbConfig()
        self.config = config

    def _generate_jwt_token(self) -> str:
        """JWT 토큰을 생성합니다."""
        payload = {
            "access_key": self.config.access_key,
            "nonce": str(uuid.uuid4()),
            "timestamp": round(time.time() * 1000),
        }
        return jwt.encode(payload, self.config.secret_key)

    def _get_headers(self) -> dict[str, str]:
        """API 요청 헤더를 생성합니다."""
        jwt_token = self._generate_jwt_token()
        return {"Authorization": f"Bearer {jwt_token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _make_api_request(self, url: str, method: str="GET", **kwargs: object) -> requests.Response:  # type: ignore[no-any-unimported]
        """API 요청을 수행합니다. (재시도 로직 포함)

        Args:
            method: HTTP 메서드 (GET, POST 등)
            url: 완전한 URL (예: "https://api.bithumb.com/v1/accounts")
            **kwargs: requests.request에 전달할 추가 인자

        Returns:
            API 응답

        Raises:
            requests.ConnectionError: 네트워크 연결 실패
            requests.Timeout: 요청 타임아웃
        """
        return requests.request(method, url, **kwargs)

    def get_balances(self) -> list[BalanceInfo]:
        """전체 계좌 잔고를 조회합니다."""
        headers = self._get_headers()
        response = self._make_api_request(f"{self.API_BASE_URL}/v1/accounts", headers=headers)

        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code}, {response.text}")

        json = response.json()
        return [BalanceInfo.from_dict(data) for data in json ]

    def get_available_amount(self, currency: str = "KRW") -> float:
        """특정 통화의 사용 가능한 잔고 조회

        Args:
            currency: 통화 코드 (기본값: "KRW")

        Returns:
            해당 통화의 잔고 (없으면 0)
        """
        balances = self.get_balances()
        return next((b.balance for b in balances if b.currency == currency), 0.0)
