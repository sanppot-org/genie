import logging
import time
from pathlib import Path
from typing import List, Tuple

import requests

from src.config import HantuConfig
from src.hantu.model import AccountType, MarketCode, access_token, balance, stock_price

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

    def get_balance(self) -> balance.BalanceResponse:
        """주식 잔고 조회

        연속 조회를 통해 모든 보유 종목과 계좌 전체 정보를 반환합니다.

        Returns:
            balance.BalanceResponse: output1(개별 종목 보유 정보), output2(계좌 전체 정보)
        """
        output1, output2 = self._get_balance_recursive()
        return balance.BalanceResponse(output1=output1, output2=output2)

    def get_stock_price(self, ticker: str, market_code: MarketCode = MarketCode.KRX) -> stock_price.ResponseBody:
        """주식 현재가 시세 조회

        Args:
            ticker: 종목코드 (예: 005930)
            market_code: 시장 분류 코드 (기본값: MarketCode.KRX)

        Returns:
            stock_price.ResponseBody: 주식 현재가 시세 정보
        """
        URL = f"{self.url_base}/uapi/domestic-stock/v1/quotations/inquire-price"

        header = stock_price.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
        )

        param = stock_price.RequestQueryParam(
            FID_COND_MRKT_DIV_CODE=market_code,
            FID_INPUT_ISCD=ticker,
        )

        # 호출
        res = requests.get(
            URL,
            headers=header.model_dump(by_alias=True),
            params=param.model_dump()
        )

        if res.status_code == 200 and res.json()["rt_cd"] == "0":
            return stock_price.ResponseBody.model_validate(res.json())
        else:
            logger.error(f"Error Code : {res.status_code} | {res.text}")
            raise Exception(f"주식 시세 조회 실패: {res.text}")

    def _get_balance_recursive(
            self,
            ctx_area_fk100: str = "",
            ctx_area_nk100: str = "",
            tr_cont: str = "",
            accumulated_output1=None,
    ) -> Tuple[List[balance.ResponseBodyoutput1], List[balance.ResponseBodyoutput2]]:
        """주식 잔고 조회 (연속 조회 지원) - 내부 메서드
        
        Args:
            ctx_area_fk100: 연속조회검색조건100 (내부적으로 사용)
            ctx_area_nk100: 연속조회키100 (내부적으로 사용)
            tr_cont: 연속거래여부 (내부적으로 사용)
            accumulated_output1: 누적된 output1 (내부적으로 사용)

        Returns:
            Tuple[List[ResponseBodyoutput1], List[ResponseBodyoutput2]]: (종목 리스트, 계좌 정보)
        """
        if accumulated_output1 is None:
            accumulated_output1 = []

        URL = f"{self.config.url_base}/uapi/domestic-stock/v1/trading/inquire-balance"

        header = balance.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=("TTTC8434R" if self.account_type == AccountType.REAL else "VTTC8434R"),
            tr_cont=tr_cont if tr_cont else "",
        )

        param = balance.RequestQueryParam(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd,
            CTX_AREA_FK100=ctx_area_fk100,
            CTX_AREA_NK100=ctx_area_nk100,
        )

        # 호출
        res = requests.get(
            URL,
            headers=header.model_dump(by_alias=True),
            params=param.model_dump()
        )

        if res.status_code == 200 and res.json()["rt_cd"] == "0":
            response_body = balance.ResponseBody.model_validate(res.json())

            # 현재 페이지 데이터 누적
            accumulated_output1.extend(response_body.output1)
            # output2는 마지막 페이지의 값을 사용 (계좌 전체 정보)
            accumulated_output2 = response_body.output2

            # 연속 조회 필요 여부 확인
            response_tr_cont = res.headers.get('tr_cont', '')

            if response_tr_cont in ['M', 'F']:  # 다음 페이지 존재
                # API 호출 간격 (과부하 방지)
                time.sleep(0.1)
                # 재귀 호출로 다음 페이지 가져오기
                return self._get_balance_recursive(
                    ctx_area_fk100=response_body.ctx_area_fk100,
                    ctx_area_nk100=response_body.ctx_area_nk100,
                    tr_cont="N",
                    accumulated_output1=accumulated_output1,
                )
            else:
                # 모든 페이지 수집 완료
                return accumulated_output1, accumulated_output2
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

        try:
            data = access_token.ResponseBody.model_validate_json(token_file.read_text())
        except Exception:
            return self._make_token()

        # 만료 체크
        if data.is_expired():
            return self._make_token()

        return data.access_token
