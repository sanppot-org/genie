import logging

import auto_runner

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

btc = "KRW-BTC"
eth = "KRW-ETH"
total_balance = 100_000_000
allocated_balance = 2_000_000

if __name__ == "__main__":
    auto_runner.run(ticker=btc, total_balance=total_balance, allocated_balance=allocated_balance)
    auto_runner.run(ticker=eth, total_balance=total_balance, allocated_balance=allocated_balance)
