import logging
from pathlib import Path

import requests

from src.config import HantuConfig
from src.hantu.model import AccountType, access_token, balance

logger = logging.getLogger(__name__)


class HantuAPI:
    """한국투자증권 API 클라이언트

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

    def get_balance(self) -> balance.ResponseBody:
        # TODO: 연속 조회 구현
        URL = f"{self.config.url_base}/uapi/domestic-stock/v1/trading/inquire-balance"

        header = balance.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=("TTTC8434R" if self.account_type == AccountType.REAL else "VTTC8434R"),
        )

        param = balance.RequestQueryParam(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd
        )

        # 호출
        res = requests.get(
            URL,
            headers=header.model_dump(by_alias=True),
            params=param.model_dump()
        )

        if res.status_code == 200 and res.json()["rt_cd"] == "0":
            return balance.ResponseBody.model_validate(res.json())

        else:
            logger.error(f"Error Code : {res.status_code} | {res.text}")
            raise Exception()

    def _make_token(self):
        """
        OAuth2 액세스 토큰 생성
        """
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

        data = access_token.ResponseBody.model_validate_json(token_file.read_text())

        # 만료 체크
        if data.is_expired():
            return self._make_token()

        return data.access_token
