import logging
from pathlib import Path

import requests
from requests import Response

from src.config import HantuConfig
from src.hantu.model import access_token
from src.hantu.model.domestic.account_type import AccountType

logger = logging.getLogger(__name__)


class HantuBaseAPI:
    """한국투자증권 API 베이스 클라이언트

    국내/해외 API에서 공통으로 사용하는 기능을 제공합니다.

    Args:
        config: 한투 API 설정
        account_type: 계좌 타입 (REAL: 실제 계좌, VIRTUAL: 가상 계좌)
    """

    def __init__(self, config: HantuConfig, account_type: AccountType = AccountType.REAL):
        self.config = config
        self.account_type = account_type

        # 계좌 타입에 따라 적절한 설정 선택
        if account_type == AccountType.REAL:
            self.cano = config.cano
            self.acnt_prdt_cd = config.acnt_prdt_cd
            self.app_key = config.app_key
            self.app_secret = config.app_secret
            self.url_base = config.url_base
            self.token_path = config.token_path
        else:  # AccountType.VIRTUAL
            self.cano = config.v_cano
            self.acnt_prdt_cd = config.v_acnt_prdt_cd
            self.app_key = config.v_app_key
            self.app_secret = config.v_app_secret
            self.url_base = config.v_url_base
            self.token_path = config.v_token_path

    def _make_token(self):
        """OAuth2 액세스 토큰 생성"""
        request_body = access_token.RequestBody(appkey=self.app_key, appsecret=self.app_secret)

        res = requests.post(url=f"{self.url_base}/oauth2/tokenP", data=request_body.model_dump_json())

        if res.status_code == 200:
            response_body = access_token.ResponseBody.model_validate(res.json())

            # 부모 디렉토리 생성
            token_file = Path(self.token_path)
            token_file.parent.mkdir(parents=True, exist_ok=True)

            # ResponseBody 전체를 JSON으로 저장
            token_file.write_text(response_body.model_dump_json())

            logger.debug(f"TOKEN : {response_body.access_token}")
            return response_body.access_token
        else:
            logger.error("Get Authentification token fail!")
            raise Exception()

    def _get_token(self) -> str:
        """토큰 로드, 없거나 만료되면 새로 생성"""
        token_file = Path(self.token_path)

        if not token_file.exists():
            return self._make_token()

        try:
            data = access_token.ResponseBody.model_validate_json(token_file.read_text())
        except Exception:
            return self._make_token()

        # 만료 체크
        if data.is_expired():
            return self._make_token()

        return data.access_token

    @staticmethod
    def _validate_response(res: Response):
        if not res or res.status_code != 200 or res.json()["rt_cd"] != "0":
            logger.error(f"Error Code : {res.status_code} | {res.text}")
            raise Exception(f"Error: {res.text}")
