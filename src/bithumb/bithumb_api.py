import time
import uuid

import jwt
import requests

from src.bithumb.model import BalanceInfo
from src.common.http_client import HTTPMethod, make_api_request
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

    def get_balances(self) -> list[BalanceInfo]:
        """전체 계좌 잔고를 조회합니다."""
        headers = self._get_headers()
        response = make_api_request(f"{self.API_BASE_URL}/v1/accounts", headers=headers)

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
