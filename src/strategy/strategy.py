import logging

from src.strategy.cache_manager import CacheManager
from src.strategy.cache_models import StrategyCache
from src.strategy.clock import Clock
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


# TODO: 할당 금액은 어떤 식으로 관리?


# 1분마다 스케줄러로 실행
class TradingService:
    def __init__(self, order_executor: OrderExecutor, config: BaseStrategyConfig, clock: Clock, collector: DataCollector) -> None:
        self._order_executor = order_executor
        self._config = config
        self._clock = clock
        self._collector = collector
        self._cache_manager = CacheManager(file_suffix="strategy")

        # 캐시 로드 시도
        loaded_cache = self._cache_manager.load_strategy_cache(config.ticker)
        today = self._clock.today()

        if not loaded_cache or loaded_cache.last_run_date != today:
            self._cache = self._update_cache()
        else:
            self._cache = loaded_cache

    def run(self) -> None:
        logger.debug("전략 실행")

        today = self._clock.today()

        logger.debug(f"오늘: {today}")

        if self._cache.last_run_date != today:
            logger.debug("날이 바뀌었습니다. 캐시를 갱신합니다.")
            self._update_cache()

        self._volatility()
        self._morning_afternoon()

    def _morning_afternoon(self) -> None:
        logger.debug("============= 오전 오후 전략 =============")

        if self._ma_should_buy():
            history = self._collector.collect_data(self._config.ticker)
            position_size = self._config.target_vol / max(history.yesterday_morning.volatility, 0.01)
            amount = min(self._config.total_balance * position_size, self._config.allocated_balance)
            result = self._order_executor.buy(self._config.ticker, amount, strategy_name="오전오후")
            self._cache.morning_afternoon_execution_volume = result.executed_volume  # 체결수량 캐시

        # 오후
        else:
            if self._cache.morning_afternoon_execution_volume:
                self._order_executor.sell(self._config.ticker, self._cache.morning_afternoon_execution_volume, strategy_name="오전오후")
                self._cache.morning_afternoon_execution_volume = 0

    def _ma_should_buy(self) -> bool:
        # 조건 1: 오전
        # 조건 2: 아직 매수 전
        # 조건 3: 전일 오후 수익률 > 0
        # 조건 4: 전일 오전 거래량 < 전일 오후 거래량
        is_morning = self._clock.is_morning()
        execution_volume = not self._cache.morning_afternoon_execution_volume

        history = self._collector.collect_data(self._config.ticker)
        afternoon_return_rate_ = history.yesterday_afternoon.return_rate > 0
        afternoon_volume = history.yesterday_morning.volume < history.yesterday_afternoon.volume

        logger.debug(f"""
        오전/오후 전략 매수 시그널:
        조건 1: 오전 = {is_morning}
        조건 2: 아직 매수 전 = {execution_volume}
        조건 3: 전일 오후 수익률 > 0 = {afternoon_return_rate_}
        조건 4: 전일 오전 거래량 < 전일 오후 거래량 = {afternoon_volume}
        """)

        return is_morning and execution_volume and afternoon_return_rate_ and afternoon_volume

    def _volatility(self) -> None:
        logger.debug("============= 변동성 돌파 전략 =============")
        if self._vol_should_buy():
            amount = min(self._config.total_balance * self._cache.volatility_position_size, self._config.allocated_balance)
            result = self._order_executor.buy(self._config.ticker, amount, strategy_name="변동성돌파")
            self._cache.volatility_execution_volume = result.executed_volume  # 체결수량 캐시

        else:
            if self._cache.volatility_execution_volume:
                self._order_executor.sell(self._config.ticker, self._cache.volatility_execution_volume, strategy_name="변동성돌파")
                self._cache.volatility_execution_volume = 0

    def _vol_should_buy(self) -> bool:
        # 조건 1: 오전
        # 조건 2: 아직 매수 전
        # 조건 3: 매수 비중 > 0
        # 조건 4: 현재가 > 돌파 가격

        is_morning = self._clock.is_morning()
        execution_volume = not self._cache.volatility_execution_volume
        position_size_ = self._cache.volatility_position_size > 0

        logger.debug(f"""
        오전/오후 전략 매수 시그널:
        조건 1: 오전 = {is_morning}
        조건 2: 아직 매수 전 = {execution_volume}
        조건 3: 매수 비중 > 0 = {position_size_}
        """)

        current_price = UpbitAPI.get_current_price(self._config.ticker)
        threshold = self._cache.volatility_threshold
        if is_morning and execution_volume and position_size_:
            logger.debug(f"조건 4: 현재가: {current_price} > 돌파 가격: {threshold} = {current_price > threshold}")

        return is_morning and execution_volume and position_size_ and current_price > threshold

    def _update_cache(self) -> StrategyCache:
        history = self._collector.collect_data(self._config.ticker)

        volatility_position_size = self._calculate_volatility_position_size(self._config.target_vol, history.yesterday_morning.volatility, history.calculate_ma_score())

        volatility_threshold = self._calculate_threshold(
            yesterday_afternoon_close=history.yesterday_afternoon.close,
            yesterday_morning_range=history.yesterday_morning.range,
            k=history.calculate_morning_noise_average(),
        )

        cache = StrategyCache(
            ticker=self._config.ticker,
            last_run_date=self._clock.today(),
            volatility_position_size=volatility_position_size,
            volatility_threshold=volatility_threshold,
        )
        logger.debug(f"캐시 업데이트: {cache}")

        # 캐시를 파일로 저장
        self._cache_manager.save_strategy_cache(self._config.ticker, cache)

        return cache

    @staticmethod
    def _calculate_threshold(yesterday_afternoon_close: float, yesterday_morning_range: float, k: float) -> float:
        return yesterday_afternoon_close + (yesterday_morning_range * k)

    @staticmethod
    def _calculate_volatility_position_size(target_vol: float, yesterday_morning_volatility: float, ma_score: float) -> float:
        # 최소: 0
        # 최대: 1
        return (target_vol / max(yesterday_morning_volatility, 0.01)) * ma_score
