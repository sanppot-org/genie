import logging

from src.strategy.base_strategy import BaseStrategy
from src.strategy.cache_models import StrategyCacheData

logger = logging.getLogger(__name__)


class MorningAfternoonStrategy(BaseStrategy[StrategyCacheData]):
    """오전/오후 전략"""

    @property
    def _strategy_name(self) -> str:
        return "morning_afternoon"

    def execute(self) -> None:
        """오전/오후 전략을 실행합니다."""
        logger.debug(f"============= {self._strategy_name} 전략 =============")

        if self._clock.is_morning():
            self._buy()

        else:
            self._sell()

    def _buy(self):
        if self._should_buy():
            history = self._collector.collect_data(self._config.ticker)
            position_size = self._config.target_vol / max(history.yesterday_morning.volatility, 0.01)
            amount = min(self._config.total_balance * position_size, self._config.allocated_balance)

            result = self._order_executor.buy(self._config.ticker, amount, strategy_name=self._strategy_name)
            self._save_cache(execution_volume=result.executed_volume)

    def _sell(self):
        # TODO: 공통 메서드로 리팩터링?
        cache = self._load_cache()
        if cache and cache.has_position(self._clock.today()):
            self._order_executor.sell(self._config.ticker, cache.execution_volume, strategy_name=self._strategy_name)
            self._delete_strategy_cache()

    def _save_cache(self, execution_volume: float) -> None:
        """기본 캐시를 저장합니다.

        Args:
            execution_volume: 체결 수량
        """
        cache = StrategyCacheData(execution_volume=execution_volume, last_run_date=self._clock.today())
        self._cache_manager.save_strategy_cache(self._config.ticker, self._strategy_name, cache)

    def _should_buy(self) -> bool:
        """오전/오후 전략의 매수 시그널을 확인합니다.

        조건:
        1. 아직 매수 전 (캐시 조회: 파일 없음 or 날짜 다름 or 수량 0)
        2. 전일 오후 수익률 > 0
        3. 전일 오전 거래량 < 전일 오후 거래량
        """

        # 1. 보유 수량 체크 (캐시 조회)
        cache = self._load_cache()
        can_buy = not cache or not cache.has_position(self._clock.today())

        # 2, 3. 전일 데이터 체크
        history = self._collector.collect_data(self._config.ticker)
        afternoon_return_rate_ = history.yesterday_afternoon.return_rate > 0
        afternoon_volume = history.yesterday_morning.volume < history.yesterday_afternoon.volume

        logger.debug(
            f"""
        오전/오후 전략 매수 시그널:
        조건 1: 기 매수 여부 = {can_buy}
        조건 2: 전일 오후 수익률 > 0 = {afternoon_return_rate_}
        조건 3: 전일 오전 거래량 < 전일 오후 거래량 = {afternoon_volume}
        """
        )

        return can_buy and afternoon_return_rate_ and afternoon_volume
