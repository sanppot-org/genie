import logging
import time
from typing import List, Tuple

import requests

from src.hantu.base_api import HantuBaseAPI
from src.hantu.model import AccountType, OverseasExchangeCode, TradingCurrencyCode, overseas_balance

logger = logging.getLogger(__name__)


class HantuOverseasAPI(HantuBaseAPI):
    """한국투자증권 해외 주식 API 클라이언트

    해외 주식 거래 및 시세 조회 기능을 제공합니다.

    Args:
        config: 한투 API 설정
        account_type: 계좌 타입 (REAL: 실제 계좌, VIRTUAL: 가상 계좌)
    """

    def get_balance(
            self,
            ovrs_excg_cd: OverseasExchangeCode = OverseasExchangeCode.NASD,
            tr_crcy_cd: TradingCurrencyCode = TradingCurrencyCode.USD,
    ) -> overseas_balance.OverseasBalanceResponse:
        """해외 주식 잔고 조회

        연속 조회를 통해 모든 보유 종목과 계좌 전체 정보를 반환합니다.

        Args:
            ovrs_excg_cd: 해외거래소코드 (OverseasExchangeCode enum 사용)
            tr_crcy_cd: 거래통화코드 (TradingCurrencyCode enum 사용)

        Returns:
            overseas_balance.OverseasBalanceResponse: output1(개별 종목), output2(계좌 전체)
        """
        output1, output2 = self._get_balance_recursive(
            ovrs_excg_cd=ovrs_excg_cd,
            tr_crcy_cd=tr_crcy_cd
        )
        return overseas_balance.OverseasBalanceResponse(output1=output1, output2=output2)

    def _get_balance_recursive(
            self,
            ovrs_excg_cd: OverseasExchangeCode,
            tr_crcy_cd: TradingCurrencyCode,
            ctx_area_fk200: str = "",
            ctx_area_nk200: str = "",
            tr_cont: str = "",
            accumulated_output1=None,
    ) -> Tuple[List[overseas_balance.ResponseBodyoutput1], overseas_balance.ResponseBodyoutput2]:
        """해외 주식 잔고 조회 (연속 조회 지원) - 내부 메서드

        Args:
            ovrs_excg_cd: 해외거래소코드 (OverseasExchangeCode enum 사용)
            tr_crcy_cd: 거래통화코드 (TradingCurrencyCode enum 사용)
            ctx_area_fk200: 연속조회검색조건200 (내부적으로 사용)
            ctx_area_nk200: 연속조회키200 (내부적으로 사용)
            tr_cont: 연속거래여부 (내부적으로 사용)
            accumulated_output1: 누적된 output1 (내부적으로 사용)

        Returns:
            Tuple: (종목 리스트, 계좌 정보)
        """
        if accumulated_output1 is None:
            accumulated_output1 = []

        URL = f"{self.url_base}/uapi/overseas-stock/v1/trading/inquire-balance"

        # TR_ID 설정 (계좌 타입에 따라 다름)
        tr_id = "TTTS3012R" if self.account_type == AccountType.REAL else "VTTS3012R"

        header = overseas_balance.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=tr_id,
            tr_cont=tr_cont if tr_cont else "",
        )

        param = overseas_balance.RequestQueryParam(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd,
            OVRS_EXCG_CD=ovrs_excg_cd,
            TR_CRCY_CD=tr_crcy_cd,
            CTX_AREA_FK200=ctx_area_fk200,
            CTX_AREA_NK200=ctx_area_nk200,
        )

        # 호출
        res = requests.get(
            URL,
            headers=header.model_dump(by_alias=True),
            params=param.model_dump()
        )

        if res.status_code == 200 and res.json()["rt_cd"] == "0":
            response_body = overseas_balance.ResponseBody.model_validate(res.json())

            # 현재 페이지 데이터 누적
            accumulated_output1.extend(response_body.output1)
            # output2는 마지막 페이지의 값을 사용 (계좌 전체 정보)
            # 연속 조회 필요 여부 확인
            response_tr_cont = res.headers.get('tr_cont', '')

            if response_tr_cont in ['M', 'F']:  # 다음 페이지 존재
                # API 호출 간격 (과부하 방지)
                time.sleep(0.1)
                # 재귀 호출로 다음 페이지 가져오기
                return self._get_balance_recursive(
                    ovrs_excg_cd=ovrs_excg_cd,
                    tr_crcy_cd=tr_crcy_cd,
                    ctx_area_fk200=response_body.ctx_area_fk200,
                    ctx_area_nk200=response_body.ctx_area_nk200,
                    tr_cont="N",
                    accumulated_output1=accumulated_output1,
                )
            else:
                # 모든 페이지 수집 완료
                return accumulated_output1, response_body.output2
        else:
            logger.error(f"Error Code : {res.status_code} | {res.text}")
            raise Exception(f"해외 주식 잔고 조회 실패: {res.text}")
