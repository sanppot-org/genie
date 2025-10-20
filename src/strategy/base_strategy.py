from abc import ABC, abstractmethod
from typing import Any, get_args, get_origin

from src.common.clock import Clock
from src.strategy.cache.cache_manager import CacheManager
from src.strategy.cache.cache_models import StrategyCacheData
from src.strategy.config import BaseStrategyConfig
from src.strategy.data.collector import DataCollector
from src.strategy.order.order_executor import OrderExecutor


class BaseStrategy[T: StrategyCacheData](ABC):
    """거래 전략의 기본 추상 클래스"""

    _cache_model_class: type[StrategyCacheData]

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        """서브클래스 정의 시 제네릭 타입 파라미터에서 캐시 모델 클래스를 추출합니다."""
        super().__init_subclass__(**kwargs)
        base = next(
            (b for b in getattr(cls, "__orig_bases__", ()) if get_origin(b) is BaseStrategy),
            None,
        )
        cls._cache_model_class = (get_args(base)[0] if base and get_args(base) else StrategyCacheData)

    def __init__(
            self,
            order_executor: OrderExecutor,
            config: BaseStrategyConfig,
            clock: Clock,
            collector: DataCollector,
            cache_manager: CacheManager,
    ) -> None:
        self._order_executor = order_executor
        self._config = config
        self._clock = clock
        self._collector = collector
        self._cache_manager = cache_manager

    @property
    @abstractmethod
    def _strategy_name(self) -> str:
        """전략 이름 (캐시 파일명에 사용)"""
        pass

    @abstractmethod
    def execute(self) -> None:
        """전략을 실행합니다."""
        pass

    def _load_cache(self) -> T | None:
        """캐시를 로드합니다.

        Returns:
            캐시 객체, 파일이 없으면 None
        """
        return self._cache_manager.load_strategy_cache(
            self._config.ticker, self._strategy_name, self._cache_model_class
        )  # type: ignore

    def _delete_strategy_cache(self) -> None:
        self._cache_manager.delete_strategy_cache(self._config.ticker, self._strategy_name)
