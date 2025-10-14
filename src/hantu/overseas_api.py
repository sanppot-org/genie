import logging
import time
from typing import List, Tuple

import requests

from src.hantu.base_api import HantuBaseAPI
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.model.domestic.order import OrderDirection
from src.hantu.model.domestic.trading_currency_code import TradingCurrencyCode
from src.hantu.model.overseas import balance as overseas_balance
from src.hantu.model.overseas import order as overseas_order
from src.hantu.model.overseas.asset_type import OverseasAssetType
from src.hantu.model.overseas.candle_period import OverseasCandlePeriod
from src.hantu.model.overseas.exchange_code import OverseasExchangeCode
from src.hantu.model.overseas.market_code import OverseasMarketCode
from src.hantu.model.overseas.minute_interval import OverseasMinuteInterval
from src.hantu.model.overseas.price import (
    OverseasCurrentPriceResponse,
    OverseasDailyCandleResponse,
    OverseasMinuteCandleResponse,
)

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

        self._validate_response(res)

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

    def get_current_price(
            self, excd: OverseasMarketCode = OverseasMarketCode.NYS, symb: str = ""
    ) -> OverseasCurrentPriceResponse:
        """해외 주식 현재체결가 조회

        Args:
            excd: 거래소코드 (OverseasMarketCode enum, 기본값: NYS)
            symb: 종목코드 (예: AAPL, TSLA 등)

        Returns:
            OverseasCurrentPriceResponse: 현재체결가 정보

        Raises:
            ValueError: 필수 파라미터가 누락된 경우
            Exception: API 호출 실패 시
        """
        if not symb:
            raise ValueError("종목코드(symb)는 필수입니다")

        URL = f"{self.url_base}/uapi/overseas-price/v1/quotations/price"
        headers = {
            "authorization": f"Bearer {self._get_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "HHDFS00000300",
        }

        params = {
            "AUTH": "",
            "EXCD": excd.value,
            "SYMB": symb,
        }

        res = requests.get(URL, headers=headers, params=params)

        self._validate_response(res)

        return OverseasCurrentPriceResponse.model_validate(res.json())

    def get_daily_candles(
            self,
            symb: str,
            start_date: str,
            end_date: str,
            excd: OverseasAssetType = OverseasAssetType.INDEX,
            period: OverseasCandlePeriod = OverseasCandlePeriod.DAILY,
    ) -> OverseasDailyCandleResponse:
        """해외 주식 일/주/월/년 캔들 데이터 조회

        Args:
            symb: 종목코드
            start_date: 시작일자 (YYYYMMDD)
            end_date: 종료일자 (YYYYMMDD)
            excd: 자산 유형 코드 (OverseasAssetType enum)
            period: 기간구분 (OverseasCandlePeriod enum, 기본값: DAILY)

        Returns:
            OverseasDailyCandleResponse: 캔들 데이터 목록

        Raises:
            ValueError: 필수 파라미터가 누락된 경우
            Exception: API 호출 실패 시
        """
        if not symb:
            raise ValueError("종목코드(symb)는 필수입니다")
        if not start_date:
            raise ValueError("시작일자(start_date)는 필수입니다")
        if not end_date:
            raise ValueError("종료일자(end_date)는 필수입니다")

        URL = f"{self.url_base}/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"
        tr_id = "FHKST03030100"

        headers = {
            "authorization": f"Bearer {self._get_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

        params = {
            "FID_COND_MRKT_DIV_CODE": excd.value,
            "FID_INPUT_ISCD": symb,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period.value,
        }

        res = requests.get(URL, headers=headers, params=params)

        self._validate_response(res)

        return OverseasDailyCandleResponse.model_validate(res.json())

    def get_minute_candles(
            self,
            symb: str,
            excd: OverseasMarketCode = OverseasMarketCode.NAS,
            nmin: OverseasMinuteInterval = OverseasMinuteInterval.MIN_1,
            include_previous: bool = False,
            limit: int = 120,
    ) -> OverseasMinuteCandleResponse:
        """해외 주식 분봉 데이터 조회

        연속 조회를 통해 모든 분봉 데이터를 반환합니다.

        Args:
            symb: 종목코드 (예: TSLA, AAPL)
            excd: 거래소코드 (기본값: NAS, OverseasMarketCode 사용)
            nmin: 분 간격 (기본값: MIN_1, OverseasMinuteInterval 사용)
            include_previous: 전일 포함 여부 (기본값: False)
            limit: 요청 개수 (최대 120, 기본값: 120)

        Returns:
            OverseasMinuteCandleResponse: 분봉 데이터 목록

        Raises:
            ValueError: 필수 파라미터가 누락된 경우
            Exception: API 호출 실패 시
        """
        if not symb:
            raise ValueError("종목코드(symb)는 필수입니다")
        if limit > 120:
            raise ValueError("요청 개수(limit)는 최대 120입니다")

        result = self._get_minute_candles_recursive(
            symb=symb,
            excd=excd,
            nmin=nmin,
            include_previous=include_previous,
            limit=limit,
        )
        return result

    def _get_minute_candles_recursive(
            self,
            symb: str,
            excd: OverseasMarketCode,
            nmin: OverseasMinuteInterval,
            include_previous: bool,
            limit: int,
            next_key: str = "",
            key_buff: str = "",
            tr_cont: str = "",
            accumulated_output2=None,
            output1_metadata=None,
    ) -> OverseasMinuteCandleResponse:
        """해외 주식 분봉 조회 (연속 조회 지원) - 내부 메서드

        Args:
            symb: 종목코드
            excd: 거래소코드 (OverseasMarketCode enum)
            nmin: 분 간격 (OverseasMinuteInterval enum)
            include_previous: 전일 포함 여부
            limit: 요청 개수 (int, 최대 120)
            next_key: 다음 조회 키
            key_buff: 키 버퍼
            tr_cont: 연속 거래 여부
            accumulated_output2: 누적된 output2 (분봉 데이터)
            output1_metadata: output1 메타데이터

        Returns:
            OverseasMinuteCandleResponse: 분봉 응답 객체
        """
        if accumulated_output2 is None:
            accumulated_output2 = []

        URL = f"{self.url_base}/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
        tr_id = "HHDFS76950200"

        headers = {
            "authorization": f"Bearer {self._get_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "tr_cont": tr_cont if tr_cont else "",
        }

        params = {
            "AUTH": "",
            "EXCD": excd.value,
            "SYMB": symb,
            "NMIN": nmin.value,
            "PINC": "1" if include_previous else "0",
            "NEXT": next_key,
            "NREC": str(limit),
            "FILL": "",
            "KEYB": key_buff,
        }

        res = requests.get(URL, headers=headers, params=params)

        self._validate_response(res)

        response_body = res.json()

        # 첫 번째 호출에서만 output1 메타데이터 저장
        if output1_metadata is None and "output1" in response_body:
            output1_metadata = response_body["output1"]

        # 현재 페이지의 분봉 데이터 누적
        if "output2" in response_body and response_body["output2"]:
            accumulated_output2.extend(response_body["output2"])

        # 연속 조회 필요 여부 확인
        response_tr_cont = res.headers.get('tr_cont', '')

        if response_tr_cont in ['M', 'F']:  # 다음 페이지 존재
            # API 호출 간격 (과부하 방지)
            time.sleep(0.1)
            # 재귀 호출로 다음 페이지 가져오기
            return self._get_minute_candles_recursive(
                symb=symb,
                excd=excd,
                nmin=nmin,
                include_previous=include_previous,
                limit=limit,
                next_key="1",
                key_buff=key_buff,
                tr_cont="N",
                accumulated_output2=accumulated_output2,
                output1_metadata=output1_metadata,
            )
        else:
            # 모든 페이지 수집 완료
            return OverseasMinuteCandleResponse(
                output1=output1_metadata,
                output2=accumulated_output2
            )

    def buy_market_order(
            self,
            ticker: str,
            quantity: int,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD
    ) -> overseas_order.ResponseBody:
        """시장가 매수 주문

        주의: 미국 시장은 시장가 매수를 지원하지 않으므로 지정가로 주문합니다.
        현재가를 조회하여 해당 가격으로 지정가 주문을 실행합니다.

        Args:
            ticker: 종목코드 (예: AAPL, TSLA)
            quantity: 주문 수량
            exchange_code: 거래소 코드 (기본값: NASD)

        Returns:
            overseas_order.ResponseBody: 주문 응답
        """
        # 현재가 조회
        price_info = self.get_current_price(
            excd=OverseasMarketCode(exchange_code.value),
            symb=ticker
        )
        current_price = price_info.output.last

        return self._order(
            ord_dv=OrderDirection.BUY,
            ord_dvsn=overseas_order.OverseasOrderDivision.LIMIT,
            exchange_code=exchange_code,
            ticker=ticker,
            quantity=quantity,
            price=current_price
        )

    def buy_limit_order(
            self,
            ticker: str,
            quantity: int,
            price: str,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD
    ) -> overseas_order.ResponseBody:
        """지정가 매수 주문

        Args:
            ticker: 종목코드 (예: AAPL, TSLA)
            quantity: 주문 수량
            price: 주문 단가
            exchange_code: 거래소 코드 (기본값: NASD)

        Returns:
            overseas_order.ResponseBody: 주문 응답
        """
        return self._order(
            ord_dv=OrderDirection.BUY,
            ord_dvsn=overseas_order.OverseasOrderDivision.LIMIT,
            exchange_code=exchange_code,
            ticker=ticker,
            quantity=quantity,
            price=price
        )

    def sell_market_order(
            self,
            ticker: str,
            quantity: int,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD
    ) -> overseas_order.ResponseBody:
        """시장가 매도 주문

        주의: 미국 시장은 시장가 매도를 지원하지 않으므로 지정가로 주문합니다.
        현재가를 조회하여 해당 가격으로 지정가 주문을 실행합니다.

        Args:
            ticker: 종목코드 (예: AAPL, TSLA)
            quantity: 주문 수량
            exchange_code: 거래소 코드 (기본값: NASD)

        Returns:
            overseas_order.ResponseBody: 주문 응답
        """
        # 현재가 조회
        price_info = self.get_current_price(
            excd=OverseasMarketCode(exchange_code.value),
            symb=ticker
        )
        current_price = price_info.output.last

        return self._order(
            ord_dv=OrderDirection.SELL,
            ord_dvsn=overseas_order.OverseasOrderDivision.LIMIT,
            exchange_code=exchange_code,
            ticker=ticker,
            quantity=quantity,
            price=current_price
        )

    def sell_limit_order(
            self,
            ticker: str,
            quantity: int,
            price: str,
            exchange_code: OverseasExchangeCode = OverseasExchangeCode.NASD
    ) -> overseas_order.ResponseBody:
        """지정가 매도 주문

        Args:
            ticker: 종목코드 (예: AAPL, TSLA)
            quantity: 주문 수량
            price: 주문 단가
            exchange_code: 거래소 코드 (기본값: NASD)

        Returns:
            overseas_order.ResponseBody: 주문 응답
        """
        return self._order(
            ord_dv=OrderDirection.SELL,
            ord_dvsn=overseas_order.OverseasOrderDivision.LIMIT,
            exchange_code=exchange_code,
            ticker=ticker,
            quantity=quantity,
            price=price
        )

    def _order(
            self,
            ord_dv: OrderDirection,
            ord_dvsn: overseas_order.OverseasOrderDivision,
            exchange_code: OverseasExchangeCode,
            ticker: str,
            quantity: int,
            price: str
    ) -> overseas_order.ResponseBody:
        """해외주식 주문 (내부 메서드)

        Args:
            ord_dv: 매수/매도 구분 (OrderDirection.BUY 또는 OrderDirection.SELL)
            ord_dvsn: 주문 구분 (OverseasOrderDivision)
            exchange_code: 거래소 코드
            ticker: 종목코드 (예: AAPL, TSLA)
            quantity: 주문 수량
            price: 주문 단가 (시장가일 경우 0)

        Returns:
            overseas_order.ResponseBody: 주문 응답
        """
        URL = f"{self.url_base}/uapi/overseas-stock/v1/trading/order"

        # TR_ID 설정 (계좌 타입, 거래소, 매수/매도 구분에 따라 다름)
        tr_id = self.ORDER_TR_ID_MAP[self.account_type, exchange_code, ord_dv]

        header = overseas_order.RequestHeader(
            authorization=f"Bearer {self._get_token()}",
            appkey=self.app_key,
            appsecret=self.app_secret,
            tr_id=tr_id,
        )

        # SLL_TYPE 설정 (매도: "00", 매수: "")
        sll_type = "00" if ord_dv == OrderDirection.SELL else ""

        body = overseas_order.RequestBody(
            CANO=self.cano,
            ACNT_PRDT_CD=self.acnt_prdt_cd,
            OVRS_EXCG_CD=exchange_code.value,
            PDNO=ticker,
            ORD_QTY=str(quantity),
            OVRS_ORD_UNPR=str(price),
            SLL_TYPE=sll_type,
            ORD_DVSN=ord_dvsn.value,
        )

        # 호출
        res = requests.post(
            URL,
            headers=header.model_dump(by_alias=True),
            data=body.model_dump_json()
        )

        self._validate_response(res)

        return overseas_order.ResponseBody.model_validate(res.json())

    # TR_ID 매핑 (계좌 타입, 거래소, 주문 방향) -> TR_ID
    ORDER_TR_ID_MAP = {
        # 미국 (NASD, NYSE, AMEX)
        (AccountType.REAL, OverseasExchangeCode.NASD, OrderDirection.BUY): "TTTT1002U",
        (AccountType.REAL, OverseasExchangeCode.NASD, OrderDirection.SELL): "TTTT1006U",
        (AccountType.REAL, OverseasExchangeCode.NYSE, OrderDirection.BUY): "TTTT1002U",
        (AccountType.REAL, OverseasExchangeCode.NYSE, OrderDirection.SELL): "TTTT1006U",
        (AccountType.REAL, OverseasExchangeCode.AMEX, OrderDirection.BUY): "TTTT1002U",
        (AccountType.REAL, OverseasExchangeCode.AMEX, OrderDirection.SELL): "TTTT1006U",
        (AccountType.VIRTUAL, OverseasExchangeCode.NASD, OrderDirection.BUY): "VTTT1002U",
        (AccountType.VIRTUAL, OverseasExchangeCode.NASD, OrderDirection.SELL): "VTTT1006U",
        (AccountType.VIRTUAL, OverseasExchangeCode.NYSE, OrderDirection.BUY): "VTTT1002U",
        (AccountType.VIRTUAL, OverseasExchangeCode.NYSE, OrderDirection.SELL): "VTTT1006U",
        (AccountType.VIRTUAL, OverseasExchangeCode.AMEX, OrderDirection.BUY): "VTTT1002U",
        (AccountType.VIRTUAL, OverseasExchangeCode.AMEX, OrderDirection.SELL): "VTTT1006U",

        # 홍콩
        (AccountType.REAL, OverseasExchangeCode.SEHK, OrderDirection.BUY): "TTTS1002U",
        (AccountType.REAL, OverseasExchangeCode.SEHK, OrderDirection.SELL): "TTTS1001U",
        (AccountType.VIRTUAL, OverseasExchangeCode.SEHK, OrderDirection.BUY): "VTTS1002U",
        (AccountType.VIRTUAL, OverseasExchangeCode.SEHK, OrderDirection.SELL): "VTTS1001U",

        # 중국 상해
        (AccountType.REAL, OverseasExchangeCode.SHAA, OrderDirection.BUY): "TTTS0202U",
        (AccountType.REAL, OverseasExchangeCode.SHAA, OrderDirection.SELL): "TTTS1005U",
        (AccountType.VIRTUAL, OverseasExchangeCode.SHAA, OrderDirection.BUY): "VTTS0202U",
        (AccountType.VIRTUAL, OverseasExchangeCode.SHAA, OrderDirection.SELL): "VTTS1005U",

        # 중국 심천
        (AccountType.REAL, OverseasExchangeCode.SZAA, OrderDirection.BUY): "TTTS0305U",
        (AccountType.REAL, OverseasExchangeCode.SZAA, OrderDirection.SELL): "TTTS0304U",
        (AccountType.VIRTUAL, OverseasExchangeCode.SZAA, OrderDirection.BUY): "VTTS0305U",
        (AccountType.VIRTUAL, OverseasExchangeCode.SZAA, OrderDirection.SELL): "VTTS0304U",

        # 일본
        (AccountType.REAL, OverseasExchangeCode.TKSE, OrderDirection.BUY): "TTTS0308U",
        (AccountType.REAL, OverseasExchangeCode.TKSE, OrderDirection.SELL): "TTTS0307U",
        (AccountType.VIRTUAL, OverseasExchangeCode.TKSE, OrderDirection.BUY): "VTTS0308U",
        (AccountType.VIRTUAL, OverseasExchangeCode.TKSE, OrderDirection.SELL): "VTTS0307U",

        # 베트남 (하노이, 호치민)
        (AccountType.REAL, OverseasExchangeCode.HASE, OrderDirection.BUY): "TTTS0311U",
        (AccountType.REAL, OverseasExchangeCode.HASE, OrderDirection.SELL): "TTTS0310U",
        (AccountType.REAL, OverseasExchangeCode.VNSE, OrderDirection.BUY): "TTTS0311U",
        (AccountType.REAL, OverseasExchangeCode.VNSE, OrderDirection.SELL): "TTTS0310U",
        (AccountType.VIRTUAL, OverseasExchangeCode.HASE, OrderDirection.BUY): "VTTS0311U",
        (AccountType.VIRTUAL, OverseasExchangeCode.HASE, OrderDirection.SELL): "VTTS0310U",
        (AccountType.VIRTUAL, OverseasExchangeCode.VNSE, OrderDirection.BUY): "VTTS0311U",
        (AccountType.VIRTUAL, OverseasExchangeCode.VNSE, OrderDirection.SELL): "VTTS0310U",
    }
