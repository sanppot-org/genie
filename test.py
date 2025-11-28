import logging

from numba.core.typeinfer import BuildTupleConstraint

from src.common.google_sheet.client import GoogleSheetClient
from src.config import GoogleSheetConfig, HantuConfig, UpbitConfig
from src.constants import KRW_BTC
from src.hantu import HantuDomesticAPI, HantuOverseasAPI
from src.hantu.model.domestic import AccountType
from src.upbit.upbit_api import UpbitAPI

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

upbit_api = UpbitAPI(UpbitConfig())  # type: ignore

hantu_domestic_api = HantuDomesticAPI(HantuConfig())  # type: ignore
hantu_overseas_api = HantuOverseasAPI(HantuConfig())  # type: ignore

v_hantu_domestic_api = HantuDomesticAPI(HantuConfig(), AccountType.VIRTUAL)  # type: ignore
v_hantu_overseas_api = HantuOverseasAPI(HantuConfig(), AccountType.VIRTUAL)  # type: ignore

google_sheet_client = GoogleSheetClient(GoogleSheetConfig(), "auto_data")

# Upbit

# result = upbit_api.get_current_price()
# result = upbit_api.get_candles()
# result = upbit_api.get_available_amount()
# result = upbit_api.get_balances()
# result = upbit_api.buy_market_order(ticker='KRW-ETH', amount=11000)
# result = upbit_api.sell_market_order(ticker='KRW-ETH', volume=0.0009) # 6000원 정도
# result = upbit_api.buy_market_order_and_wait(ticker='KRW-ETH', amount=5000)
# result = upbit_api.sell_market_order_and_wait(ticker='KRW-ETH', volume=0.0009)
# result = upbit_api.upbit.get_order('e9e04adc-b0dc-47a4-bd98-ff544e2846da')
# result = upbit_api.buy_best_fok_order_and_wait(KRW_BTC, 6000)
# result = upbit_api.sell_best_ioc_order_and_wait(KRW_BTC, 0.00004417)
# print(result)

#################################### KIS ####################################
### Domastic ###

# result = hantu_domestic_api.get_balance()
# result = result.output1[0].to_simple()
# result = hantu_domestic_api.get_stock_price(ticker='005930')
# result = hantu_domestic_api.get_psbl_order(ticker='005930', price='55000')
# result = hantu_domestic_api.get_daily_chart(ticker='005930', start_date=date(2025, 10, 1), end_date=date(2025, 10, 3), interval=ChartInterval.DAY)
# result = hantu_domestic_api.get_minute_chart(ticker='005930', target_date=date(2025, 10, 1), target_time=time(13, 0, 0))

## Order ##
# result = hantu_domestic_api.buy_market_order(ticker='005930', quantity=1)  # 1주 매수
# result = hantu_domestic_api.buy_limit_order(ticker='005930', quantity=1, price=93000)
# result = hantu_domestic_api.sell_market_order(ticker='005930', quantity=9990)  # 1만원으로 시도
# result = hantu_domestic_api.sell_limit_order(ticker='005930', quantity=1, price=92000)


### Overseas ###

# result = hantu_overseas_api.get_balance()
# result = hantu_overseas_api.get_current_price(excd=OverseasMarketCode.NAS, symb="QQQ")
# result = hantu_overseas_api.get_minute_candles(symb='AAPL')
# result = v_hantu_overseas_api.get_minute_candles(symb='AAPL')


#################################### Candle ####################################

# clock = SystemClock()
# collector = DataCollector(clock)
# result = collector.collect_data("KRW-BTC", days=20)

###### storage #########
# ticker = "KRW-BTC"
# filename = f"{ticker}-{datetime.now().date()}.json"
# data = collector.collect_initial_data(ticker=ticker)
# storage.save(data, filename)

# result = storage.load(filename)

### Strategy ###
# history = storage.load(filename)
# result = morning_afternoon.check_buy_signal(history=history)

# breakout_strategy = VolatilityBreakoutStrategy()  # 필요한 인자 추가 필요

# result = breakout_strategy._check_buy_signal(history=history, current_price=get_current_price())


# executor = OrderExecutor(upbit_api=upbit_api, google_sheet_client=GoogleSheetClient(GoogleSheetConfig()), slack_client=SlackClient(SlackConfig()))

# executor.buy(ticker="KRW-ETH", amount=5100, strategy_name="테스트")
# executor.sell(ticker="KRW-ETH", volume=0.00086352, strategy_name="테스트")

### SLACK ###

# slack_client = SlackClient(SlackConfig())
# slack_client.send_message("hi")

# print(result)

### report ###
# reporter = Reporter(upbit_api=upbit_api, hantu_api=hantu_domestic_api, slack_cient=SlackClient(SlackConfig()))
# reporter.report()

# 2. 국내 금가격 - HantuAPI
# chart_response = hantu_domestic_api.get_daily_chart("M04020000", yesterday, today)
# print(chart_response)

### google sheet data collector ###
# GoogleSheetDataCollector(hantu_api=hantu_domestic_api, google_sheet_client=google_sheet_client).collect_price()
