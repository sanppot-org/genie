import logging

from src.strategy.base_strategy import BaseStrategy
from src.strategy.cache.cache_models import VolatilityStrategyCacheData
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


# TODO: 탬플릿 메서드 패턴 적용
class VolatilityStrategy(BaseStrategy[VolatilityStrategyCacheData]):
    """변동성 돌파 전략"""

    @property
    def _strategy_name(self) -> str:
        return "volatility"

    def execute(self) -> None:
        """변동성 돌파 전략을 실행합니다."""
        if self._clock.is_morning():
            self._buy()

        else:
            self._sell()

    def _buy(self) -> None:
        position_size, threshold, has_position = self._get_strategy_params()

        if self._should_buy(position_size, threshold, has_position):
            amount = min(
                self._config.total_balance * position_size,
                self._config.allocated_balance,
            )

            result = self._order_executor.buy(self._config.ticker, amount, strategy_name=self._strategy_name)

            # FOK 체결 성공 시에만 캐시 저장
            if result.executed_volume > 0:
                self._save_cache(execution_volume=result.executed_volume, position_size=position_size, threshold=threshold)

    def _sell(self) -> None:
        cache = self._load_cache()
        if cache and cache.has_position(self._clock.today()):
            result = self._order_executor.sell(
                self._config.ticker,
                cache.execution_volume,
                strategy_name=self._strategy_name
            )

            if result.executed_volume <= 0:
                return

            remaining_volume = cache.execution_volume - result.executed_volume

            if remaining_volume <= 0:
                self._delete_strategy_cache()
                return

            # 부분 체결: 남은 수량으로 캐시 업데이트
            self._save_cache(
                execution_volume=remaining_volume,
                position_size=cache.position_size,
                threshold=cache.threshold
            )

    def _get_strategy_params(self) -> tuple[float, float, bool]:
        """전략 파라미터를 캐시에서 가져오거나 새로 계산합니다.

        캐시가 없거나 날짜가 다르면 계산 후 execution_volume=0으로 저장합니다.

        Returns:
            (position_size, threshold, has_position) 튜플
        """
        cache = self._load_cache()

        if cache and cache.last_run_date == self._clock.today():
            return cache.position_size, cache.threshold, cache.has_position(self._clock.today())

        # 계산
        history = self._collector.collect_data(self._config.ticker)
        position_size = self._calculate_volatility_position_size(self._config.target_vol, history.yesterday_morning.volatility, history.calculate_ma_score())
        threshold = self._calculate_threshold(
            yesterday_afternoon_close=history.yesterday_afternoon.close,
            yesterday_morning_range=history.yesterday_morning.range,
            k=history.calculate_morning_noise_average(),
        )

        self._save_cache(execution_volume=0, position_size=position_size, threshold=threshold)

        return position_size, threshold, False

    def _should_buy(self, position_size: float, threshold: float, has_position: bool) -> bool:
        """변동성 돌파 전략의 매수 시그널을 확인합니다.

        조건:
        1. 아직 매수 전 (캐시 조회: 파일 없음 or 날짜 다름 or 수량 0)
        2. 매수 비중 > 0
        3. 현재가 > 돌파 가격
        """
        position_size_valid = position_size > 0

        # TODO: 매번 찍지 않기
        logger.info(
            f"""
        변동성 돌파 전략 매수 시그널:
        조건 1: 기 매수 여부 = {has_position}
        조건 2: 매수 비중 > 0 = {position_size_valid}
        """
        )

        if has_position or not position_size_valid:
            return False

        # 4. 현재가 > 돌파 가격
        current_price = UpbitAPI.get_current_price(self._config.ticker)
        price_breakout = current_price > threshold

        logger.info(f"조건 3: 현재가: {current_price} > 돌파 가격: {threshold} = {price_breakout}")

        return price_breakout

    def _save_cache(self, execution_volume: float, position_size: float, threshold: float) -> None:
        """변동성 전략 전용 캐시를 저장합니다.

        Args:
            execution_volume: 체결 수량
            position_size: 매수 비중
            threshold: 돌파 가격
        """
        cache = VolatilityStrategyCacheData(
            execution_volume=execution_volume,
            last_run_date=self._clock.today(),
            position_size=position_size,
            threshold=threshold,
        )
        self._cache_manager.save_strategy_cache(self._config.ticker, self._strategy_name, cache)

    @staticmethod
    def _calculate_threshold(yesterday_afternoon_close: float, yesterday_morning_range: float, k: float) -> float:
        """돌파 가격을 계산합니다."""
        return yesterday_afternoon_close + (yesterday_morning_range * k)

    @staticmethod
    def _calculate_volatility_position_size(target_vol: float, yesterday_morning_volatility: float, ma_score: float) -> float:
        """매수 비중을 계산합니다.

        Returns:
            0 ~ 1 사이의 값
        """
        return min(
            (target_vol / max(yesterday_morning_volatility, 0.01)) * ma_score,
            1.0,
        )
