from src.strategy.clock import SystemClock

from src.strategy.data.collector import DataCollector
from src.upbit.upbit_api import UpbitAPI

clock = SystemClock()
collector = DataCollector(clock)
ticker = 'KRW-BTC'
target_vol = 0.001 # [0.5%, 1%, 2%]
upbit_api = UpbitAPI()
krw_balance = upbit_api.get_available_amount() / 2 - 1000
history = collector.collect_data(ticker, days=20)
total_krw_balance = 1

# 1분마다 스케줄러로 실행. 각 전략 실행 여부를 저장해둔다.
# 날짜를 저장해두고 날이 바뀐 경우 캐시를 업데이트 한다.

# TODO: 멱등하게 동작하도록.
def volatility():
    # 오전
    if clock.is_morning():
        # TODO: 이미 매수한 경우 멈추기
        position_size = calculate_volatility_position_size() # TODO: 캐시
        threshold = calculate_threshold() # TODO: 캐시

        if position_size > 0 and UpbitAPI.get_current_price(ticker) > threshold:
            # 매수
            amount = min(total_krw_balance * position_size, krw_balance)
            upbit_api.buy_market_order(ticker, amount)

    # 오후
    else:
        upbit_api.sell_all(ticker)


def calculate_threshold() -> float:
    today_open = history.yesterday_afternoon.close
    k = history.calculate_morning_noise_average()
    return today_open + (history.yesterday_morning.range * k)


def calculate_volatility_position_size() -> float:
    # 최소: 0
    # 최대: 1
    return (target_vol / max(history.yesterday_morning.volatility, 0.01)) * history.calculate_ma_score()


# TODO: 멱등하게 동작하도록
def morning_afternoon():
    # 오전
    if clock.is_morning():
        # 조건 1: 전일 오후 수익률 > 0
        # 조건 2: 전일 오전 거래량 < 전일 오후 거래량
        if history.yesterday_afternoon.return_rate > 0 and history.yesterday_morning.volume < history.yesterday_afternoon.volume:
            position_size = target_vol / max(history.yesterday_morning.volatility, 0.01)
            amount = min(total_krw_balance * position_size, krw_balance)
            upbit_api.buy_market_order(ticker, amount)

    # 오후
    else:
        upbit_api.sell_all(ticker)
