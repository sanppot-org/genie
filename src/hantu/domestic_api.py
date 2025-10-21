import logging
import time
from datetime import date
from datetime import time as time_obj

import requests

from src.common.order_direction import OrderDirection
from src.hantu.base_api import HantuBaseAPI
from src.hantu.model.domestic import balance, chart, order, psbl_order, stock_price
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.model.domestic.chart import ChartInterval, PriceType
from src.hantu.model.domestic.market_code import MarketCode
from src.hantu.model.domestic.order import OrderDivision

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

    def get_psbl_order(
            self,
            ticker: str,
            price: str,
            order_division: OrderDivision = OrderDivision.MARKET,
            cma_evaluation_amount_included: str = "N",
            overseas_included: str = "N",
    ) -> psbl_order.ResponseBody:
        """매수가능 조회

        특정 종목의 매수 가능 금액과 수량을 조회합니다.

        Args:
            ticker: 종목코드 (예: 005930)
            price: 주문단가 (1주당 가격)
            order_division: 주문구분 (기본값: MARKET - 시장가)
            cma_evaluation_amount_included: CMA평가금액포함여부 (기본값: N)
            overseas_included: 해외포함여부 (기본값: N)

        Returns:
            psbl_order.ResponseBody: 매수가능 조회 결과
        """
        url = f"{self.url_base}/uapi/domestic-stock/v1/trading/inquire-psbl-order"

        # TR_ID 설정 (계좌 타입에 따라 다름)
        tr_id = "TTTC8908R" if self.account_type == AccountType.REAL else "VTTC8908R"

        header = psbl_order.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=tr_id,
        )

        param = psbl_order.RequestQueryParam(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd,
            PDNO=ticker,
            ORD_UNPR=price,
            ORD_DVSN=order_division.value,
            CMA_EVLU_AMT_ICLD_YN=cma_evaluation_amount_included,
            OVRS_ICLD_YN=overseas_included,
        )

        # 호출
        res = requests.get(url, headers=header.model_dump(by_alias=True), params=param.model_dump())

        self._validate_response(res)

        return psbl_order.ResponseBody.model_validate(res.json())

    def get_stock_price(self, ticker: str, market_code: MarketCode = MarketCode.KRX) -> stock_price.ResponseBody:
        """주식 현재가 시세 조회

        Args:
            ticker: 종목코드 (예: 005930)
            market_code: 시장 분류 코드 (기본값: MarketCode.KRX)

        Returns:
            stock_price.ResponseBody: 주식 현재가 시세 정보
        """
        url = f"{self.url_base}/uapi/domestic-stock/v1/quotations/inquire-price"

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
        res = requests.get(url, headers=header.model_dump(by_alias=True), params=param.model_dump())

        self._validate_response(res)

        return stock_price.ResponseBody.model_validate(res.json())

    def sell_market_order(self, ticker: str, quantity: int) -> order.ResponseBody:
        """시장가 매도 주문

        Args:
            ticker: 종목코드 (예: 005930)
            quantity: 주문 수량

        Returns:
            order.ResponseBody: 주문 응답
        """
        return self._order(
            order_direction=OrderDirection.SELL,
            order_division=OrderDivision.MARKET,
            ticker=ticker,
            quantity=quantity,
            price=0,
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
            order_direction=OrderDirection.SELL,
            order_division=OrderDivision.LIMIT,
            ticker=ticker,
            quantity=quantity,
            price=price,
        )

    def buy_market_order(self, ticker: str, quantity: int) -> order.ResponseBody:
        """시장가 매수 주문

        Args:
            ticker: 종목코드 (예: 005930)
            quantity: 매수 수량 (주)

        Returns:
            order.ResponseBody: 주문 응답
        """
        return self._order(
            order_direction=OrderDirection.BUY,
            order_division=OrderDivision.MARKET,
            ticker=ticker,
            quantity=quantity,
            price=0,
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
            order_direction=OrderDirection.BUY,
            order_division=OrderDivision.LIMIT,
            ticker=ticker,
            quantity=quantity,
            price=price,
        )

    def _order(self, order_direction: OrderDirection, order_division: OrderDivision, ticker: str, quantity: int, price: int) -> order.ResponseBody:
        """주식 주문 (내부 메서드)

        Args:
            order_direction: 매수/매도 구분 (OrderDirection.BUY 또는 OrderDirection.SELL)
            order_division: 주문 구분 (OrderDivision.LIMIT 또는 OrderDivision.MARKET)
            ticker: 종목코드 (예: 005930)
            quantity: 주문 수량
            price: 주문 단가 (시장가일 경우 0)

        Returns:
            order.ResponseBody: 주문 응답
        """
        url = f"{self.url_base}/uapi/domestic-stock/v1/trading/order-cash"

        # TR_ID 설정 (계좌 타입과 매수/매도 구분에 따라 다름)
        tr_id = self.ORDER_TR_ID_MAP[self.account_type, order_direction]  # type: ignore[index]

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
            ORD_DVSN=order_division.value,
            ORD_QTY=str(quantity),
            ORD_UNPR=str(price),
        )

        # 호출
        res = requests.post(url, headers=header.model_dump(by_alias=True), data=body.model_dump_json())

        self._validate_response(res)

        return order.ResponseBody.model_validate(res.json())

    def _get_balance_recursive(
            self,
            ctx_area_fk100: str = "",
            ctx_area_nk100: str = "",
            continuation_flag: str = "",
            accumulated_output1: list[balance.ResponseBodyoutput1] | None = None,
    ) -> tuple[list[balance.ResponseBodyoutput1], list[balance.ResponseBodyoutput2]]:
        """주식 잔고 조회 (연속 조회 지원) - 내부 메서드

        Args:
            ctx_area_fk100: 연속조회검색조건100 (내부적으로 사용)
            ctx_area_nk100: 연속조회키100 (내부적으로 사용)
            continuation_flag: 연속거래여부 (내부적으로 사용)
            accumulated_output1: 누적된 output1 (내부적으로 사용)

        Returns:
            Tuple[List[ResponseBodyoutput1], List[ResponseBodyoutput2]]: (종목 리스트, 계좌 정보)
        """
        if accumulated_output1 is None:
            accumulated_output1 = []

        url = f"{self.url_base}/uapi/domestic-stock/v1/trading/inquire-balance"

        header = balance.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=("TTTC8434R" if self.account_type == AccountType.REAL else "VTTC8434R"),
            tr_cont=continuation_flag if continuation_flag else "",
        )

        param = balance.RequestQueryParam(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd,
            CTX_AREA_FK100=ctx_area_fk100,
            CTX_AREA_NK100=ctx_area_nk100,
        )

        # 호출
        res = requests.get(url, headers=header.model_dump(by_alias=True), params=param.model_dump())

        self._validate_response(res)

        response_body = balance.ResponseBody.model_validate(res.json())

        # 현재 페이지 데이터 누적
        accumulated_output1.extend(response_body.output1)
        # output2는 마지막 페이지의 값을 사용 (계좌 전체 정보)
        accumulated_output2 = response_body.output2

        # 연속 조회 필요 여부 확인
        response_tr_cont = res.headers.get("tr_cont", "")

        if response_tr_cont in ["M", "F"]:  # 다음 페이지 존재
            # API 호출 간격 (과부하 방지)
            time.sleep(0.1)
            # 재귀 호출로 다음 페이지 가져오기
            return self._get_balance_recursive(
                ctx_area_fk100=response_body.ctx_area_fk100,
                ctx_area_nk100=response_body.ctx_area_nk100,
                continuation_flag="N",
                accumulated_output1=accumulated_output1,
            )
        else:
            # 모든 페이지 수집 완료
            return accumulated_output1, accumulated_output2

    def get_daily_chart(
            self,
            ticker: str,
            start_date: date,
            end_date: date,
            interval: ChartInterval = ChartInterval.DAY,
            price_type: PriceType = PriceType.ADJUSTED,
            market_code: MarketCode = MarketCode.KRX,
    ) -> chart.DailyChartResponseBody:
        """일/주/월/년봉 차트 조회

        Args:
            ticker: 종목코드 (예: 005930)
            start_date: 조회 시작일자 (date 객체)
            end_date: 조회 종료일자 (date 객체, 최대 100개)
            interval: 차트 주기 (기본값: DAY - 일봉)
            price_type: 가격 타입 (기본값: ADJUSTED - 수정주가)
            market_code: 시장 분류 코드 (기본값: KRX)

        Returns:
            chart.DailyChartResponseBody: 일/주/월/년봉 차트 데이터
        """
        url = f"{self.url_base}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

        header = chart.DailyChartRequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
        )

        param = chart.DailyChartRequestQueryParam(
            FID_COND_MRKT_DIV_CODE=market_code,
            FID_INPUT_ISCD=ticker,
            FID_INPUT_DATE_1=start_date.strftime("%Y%m%d"),
            FID_INPUT_DATE_2=end_date.strftime("%Y%m%d"),
            FID_PERIOD_DIV_CODE=interval,
            FID_ORG_ADJ_PRC=price_type,
        )

        # 호출
        res = requests.get(url, headers=header.model_dump(by_alias=True), params=param.model_dump())

        self._validate_response(res)

        return chart.DailyChartResponseBody.model_validate(res.json())

    def get_minute_chart(self, ticker: str, target_date: date, target_time: time_obj, market_code: MarketCode = MarketCode.KRX) -> chart.MinuteChartResponseBody:
        """분봉 차트 조회

        - 한 번 호출에 최대 120건

        Args:
            ticker: 종목코드 (예: 005930)
            target_date: 조회 일자 (date 객체)
            target_time: 조회 시간 (time 객체)
            market_code: 시장 분류 코드 (기본값: KRX)

        Returns:
            chart.MinuteChartResponseBody: 분봉 차트 데이터
        """
        url = f"{self.url_base}/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"

        header = chart.MinuteChartRequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
        )

        param = chart.MinuteChartRequestQueryParam(
            FID_COND_MRKT_DIV_CODE=market_code,
            FID_INPUT_ISCD=ticker,
            FID_INPUT_HOUR_1=target_time.strftime("%H%M%S"),
            FID_INPUT_DATE_1=target_date.strftime("%Y%m%d"),
        )

        # 호출
        res = requests.get(url, headers=header.model_dump(by_alias=True), params=param.model_dump())

        self._validate_response(res)

        return chart.MinuteChartResponseBody.model_validate(res.json())

    # TR_ID 매핑 (계좌 타입, 주문 방향) -> TR_ID
    ORDER_TR_ID_MAP = {
        (AccountType.REAL, OrderDirection.SELL): "TTTC0011U",  # 실전 매도
        (AccountType.REAL, OrderDirection.BUY): "TTTC0012U",  # 실전 매수
        (AccountType.VIRTUAL, OrderDirection.SELL): "VTTC0011U",  # 모의 매도
        (AccountType.VIRTUAL, OrderDirection.BUY): "VTTC0012U",  # 모의 매수
    }
