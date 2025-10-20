import logging

from src.common.slack.client import SlackClient
from src.config import SlackConfig
from src.strategy import o_dol_strategy

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# TODO: DB 설정
total_balance = 100_000_000
allocated_balance = 1_000_000

if __name__ == "__main__":
    slack_client = SlackClient(SlackConfig())
    slack_client.send_debug("암호화폐 자동 매매 실행")  # 로그 남기기

    o_dol_strategy.run(ticker="KRW-BTC", total_balance=100_000_000, allocated_balance=1_000_000)
    o_dol_strategy.run(ticker="KRW-ETH", total_balance=100_000_000, allocated_balance=1_000_000)
    o_dol_strategy.run(ticker="KRW-XRP", total_balance=100_000_000, allocated_balance=1_000_000)
    o_dol_strategy.run(ticker="KRW-USDT", total_balance=100_000_000, allocated_balance=1_000_000)
