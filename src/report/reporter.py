import logging

from src.collector.data_fetcher import fetch_finance_data_reader, fetch_yfinance
from src.common.slack.client import SlackClient
from src.hantu import HantuDomesticAPI
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


class Reporter:
    def __init__(self, upbit_api: UpbitAPI, hantu_api: HantuDomesticAPI, slack_cient: SlackClient) -> None:
        self.upbit_api = upbit_api
        self.hantu_api = hantu_api
        self.slack_client = slack_cient

    @staticmethod
    def _get_trend_emoji(change_rate: float) -> str:
        """변화율에 따른 추세 이모지 반환"""
        if change_rate > 0.1:
            return "↗️"
        elif change_rate < -0.1:
            return "↘️"
        else:
            return "➡️"

    def report(self) -> None:
        """금/환율/프리미엄 리포트를 Slack으로 전송.

        프리미엄은 여러 소스를 교차 계산하므로 부분 전송이 성립하지 않는다. 외부 소스
        (yfinance/KIS/FDR/Upbit)가 장애·점검으로 실패하면 이번 사이클 리포트를 스킵하고
        한 줄 warning만 남긴다(크래시 안 함).
        """
        try:
            self._build_and_send_report()
        except Exception as e:  # noqa: BLE001 — 스케줄 잡, 외부 소스 실패 시 이번 사이클만 스킵
            logger.warning("리포트 생성 실패, 이번 사이클 스킵: %s", e)

    def _build_and_send_report(self) -> None:
        # 1. 환율 (KRW/USD) - yfinance
        krw_usd_today = float(fetch_yfinance('KRW=X')['Close'].iloc[-1])

        # 2. 국내 금가격 - HantuAPI
        domestic_gold_today = float(self.hantu_api.get_stock_price(ticker="M04020000").output.stck_prpr)

        # 3. 국제 금가격 - FinanceDataReader
        intl_gold_today = float(fetch_finance_data_reader('GC=F')['Close'].iloc[-1] / 31.1 * krw_usd_today)

        # 4. USDT - UpbitAPI
        usdt_today = float(self.upbit_api.get_current_price("KRW-USDT"))

        # 프리미엄 계산
        gold_premium = (domestic_gold_today / intl_gold_today - 1) * 100
        dollar_premium = (usdt_today / krw_usd_today - 1) * 100

        message = f"""
💰 금 가격
국내: {domestic_gold_today:,.0f})
국제: {intl_gold_today:,.0f})
프리미엄: {gold_premium:.2f}%

💱 환율/암호화폐
USDT: {usdt_today:,.2f})
환율: {krw_usd_today:,.2f})
달러 프리미엄: {dollar_premium:.2f}%
        """

        self.slack_client.send_report(message)
