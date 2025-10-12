import logging
import time
from typing import List, Tuple

import requests

from src.hantu.base_api import HantuBaseAPI
from src.hantu.model import AccountType, MarketCode, balance, order, stock_price
from src.hantu.model.order import OrderDirection, OrderDivision

logger = logging.getLogger(__name__)


class HantuDomesticAPI(HantuBaseAPI):
    """한국투자증권 국내 주식 API 클라이언트

    국내 주식 거래 및 시세 조회 기능을 제공합니다.

    Args:
        config: 한투 API 설정
        account_type: 계좌 타입 (REAL: 실제 계좌, VIRTUAL: 가상 계좌)
    """

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

    def sell_market_order(self, ticker: str, quantity: int) -> order.ResponseBody:
        """시장가 매도 주문

        Args:
            ticker: 종목코드 (예: 005930)
            quantity: 주문 수량

        Returns:
            order.ResponseBody: 주문 응답
        """
        return self._order(
            ord_dv=OrderDirection.SELL,
            ord_dvsn=OrderDivision.MARKET,
            ticker=ticker,
            quantity=quantity,
            price=0
        )

    def sell_limit_order(self, ticker: str, quantity: int, price: int) -> order.ResponseBody:
        """지정가 매도 주문

        Args:
            ticker: 종목코드 (예: 005930)
            quantity: 주문 수량
            price: 주문 단가

        Returns:
            order.ResponseBody: 주문 응답
        """
        return self._order(
            ord_dv=OrderDirection.SELL,
            ord_dvsn=OrderDivision.LIMIT,
            ticker=ticker,
            quantity=quantity,
            price=price
        )

    def buy_market_order(self, ticker: str, price: int) -> order.ResponseBody:
        """시장가 매수 주문

        Args:
            ticker: 종목코드 (예: 005930)
            price: 매수 금액 (원)

        Returns:
            order.ResponseBody: 주문 응답
        """
        return self._order(
            ord_dv=OrderDirection.BUY,
            ord_dvsn=OrderDivision.MARKET,
            ticker=ticker,
            quantity=price,  # 시장가 매수는 매수 금액을 수량 필드에 전달
            price=0
        )

    def buy_limit_order(self, ticker: str, quantity: int, price: int) -> order.ResponseBody:
        """지정가 매수 주문

        Args:
            ticker: 종목코드 (예: 005930)
            quantity: 주문 수량
            price: 주문 단가

        Returns:
            order.ResponseBody: 주문 응답
        """
        return self._order(
            ord_dv=OrderDirection.BUY,
            ord_dvsn=OrderDivision.LIMIT,
            ticker=ticker,
            quantity=quantity,
            price=price
        )

    def _order(
            self,
            ord_dv: OrderDirection,
            ord_dvsn: OrderDivision,
            ticker: str,
            quantity: int,
            price: int
    ) -> order.ResponseBody:
        """주식 주문 (내부 메서드)

        Args:
            ord_dv: 매수/매도 구분 (OrderDirection.BUY 또는 OrderDirection.SELL)
            ord_dvsn: 주문 구분 (OrderDivision.LIMIT 또는 OrderDivision.MARKET)
            ticker: 종목코드 (예: 005930)
            quantity: 주문 수량
            price: 주문 단가 (시장가일 경우 0)

        Returns:
            order.ResponseBody: 주문 응답
        """
        URL = f"{self.url_base}/uapi/domestic-stock/v1/trading/order-cash"

        # TR_ID 설정 (계좌 타입과 매수/매도 구분에 따라 다름)
        tr_id = self.ORDER_TR_ID_MAP[self.account_type, ord_dv]  # type: ignore[index]

        header = order.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=tr_id,
        )

        body = order.RequestBody(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd,
            PDNO=ticker,
            ORD_DVSN=ord_dvsn.value,
            ORD_QTY=str(quantity),
            ORD_UNPR=str(price),
        )

        # 호출
        res = requests.post(
            URL,
            headers=header.model_dump(by_alias=True),
            data=body.model_dump_json()
        )

        if res.status_code == 200:
            response_body = order.ResponseBody.model_validate(res.json())
            if response_body.rt_cd != "0":
                logger.error(f"주문 실패: {response_body.msg1}")
                raise Exception(f"주문 실패: {response_body.msg1}")
            return response_body
        else:
            logger.error(f"Error Code : {res.status_code} | {res.text}")
            raise Exception(f"주식 주문 실패: {res.text}")

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

        URL = f"{self.url_base}/uapi/domestic-stock/v1/trading/inquire-balance"

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

    # TR_ID 매핑 (계좌 타입, 주문 방향) -> TR_ID
    ORDER_TR_ID_MAP = {
        (AccountType.REAL, OrderDirection.SELL): "TTTC0011U",  # 실전 매도
        (AccountType.REAL, OrderDirection.BUY): "TTTC0012U",  # 실전 매수
        (AccountType.VIRTUAL, OrderDirection.SELL): "VTTC0011U",  # 모의 매도
        (AccountType.VIRTUAL, OrderDirection.BUY): "VTTC0012U",  # 모의 매수
    }
