from datetime import datetime, timedelta

import FinanceDataReader as fdr  # noqa: N813
import yfinance as yf

from src.common.slack.client import SlackClient
from src.hantu import HantuDomesticAPI
from src.upbit.upbit_api import UpbitAPI


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
        # 날짜 계산
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        # 1. 환율 (KRW/USD) - yfinance
        krw_history = yf.Ticker('KRW=X').history(period='1d')
        krw_usd_today = float(krw_history['Close'].iloc[-1])

        # 2. 국내 금가격 - HantuAPI
        domestic_gold_price = self.hantu_api.get_stock_price(ticker="M04020000")
        domestic_gold_today = float(domestic_gold_price.output.stck_prpr)

        # 3. 국제 금가격 - FinanceDataReader
        gold_df = fdr.DataReader('GC=F', str(yesterday), str(today))
        intl_gold_today = float(gold_df['Close'].iloc[-1] / 31.1 * krw_usd_today)

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
