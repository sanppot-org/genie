import logging
from datetime import date, time

from src.config import UpbitConfig, HantuConfig
from src.hantu import HantuDomesticAPI, HantuOverseasAPI
from src.hantu.model.domestic import AccountType
from src.upbit.upbit_api import UpbitAPI

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

upbit_api = UpbitAPI(UpbitConfig())  # type: ignore
hantu_domestic_api = HantuDomesticAPI(HantuConfig(), AccountType.VIRTUAL)  # type: ignore
hantu_overseas_api = HantuOverseasAPI(HantuConfig(), AccountType.VIRTUAL)  # type: ignore
# result = get_current_price()
# result = get_candles()

# Upbit

# result = upbit_api.get_balance()
# result = upbit_api.get_balances()
# result = upbit_api.buy_market_order(ticker='KRW-ETH', price=11000)
# result = upbit_api.sell_market_order(ticker='KRW-ETH', volume=0.0009) # 6000원 정도

#################################### KIS ####################################
### Domastic ###

# result = hantu_domestic_api.get_balance()
# result = result.output1[0].to_simple()
# result = hantu_domestic_api.get_stock_price(ticker='005930')
# result = hantu_domestic_api.get_psbl_order(ticker='005930', price='55000')
# result = hantu_domestic_api.get_daily_chart(ticker='005930', start_date=date(2025, 10, 1), end_date=date(2025, 10, 3), interval=ChartInterval.DAY)
result = hantu_domestic_api.get_minute_chart(ticker='005930', target_date=date(2025, 10, 1), target_time=time(13, 0, 0))

## Order ##
# result = hantu_domestic_api.buy_market_order(ticker='005930', quantity=1)  # 1주 매수
# result = hantu_domestic_api.buy_limit_order(ticker='005930', quantity=1, price=93000)
# result = hantu_domestic_api.sell_market_order(ticker='005930', quantity=9990)  # 1만원으로 시도
# result = hantu_domestic_api.sell_limit_order(ticker='005930', quantity=1, price=92000)


#################################### Overseas ####################################

# result = hantu_overseas_api.get_balance()
# result = hantu_overseas_api.get_current_price(excd=OverseasMarketCode.NAS, symb="QQQ")


print(result)
