import logging

from src.config import UpbitConfig, HantuConfig
from src.hantu import HantuDomesticAPI, HantuOverseasAPI
from src.hantu.model.domestic import AccountType

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
from src.upbit.upbit_api import UpbitAPI

upbit_api = UpbitAPI(UpbitConfig())  # type: ignore
hantu_domestic_api = HantuDomesticAPI(HantuConfig(), AccountType.VIRTUAL)  # type: ignore
hantu_overseas_api = HantuOverseasAPI(HantuConfig(), AccountType.VIRTUAL)  # type: ignore
# result = get_current_price()
# result = get_candles()


# result = upbit_api.get_balance()
# result = upbit_api.get_balances()
# result = upbit_api.buy_market_order(ticker='KRW-ETH', price=11000)
# result = upbit_api.sell_market_order(ticker='KRW-ETH', volume=0.0009) # 6000원 정도

# result = hantu_domestic_api.get_balance()
result = hantu_overseas_api.get_balance()
# result = hantu_api.buy_market_order(ticker='005930', price=100000)
# result = hantu_api.get_stock_price(ticker='005930')


print(result)
