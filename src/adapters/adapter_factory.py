"""Adapter factory for selecting the appropriate candle data adapter."""

from src.common.data_adapter import CandleDataAdapter, DataSource

from .candle_adapters import BinanceCandleAdapter, HantuCandleAdapter, UpbitCandleAdapter


class CandleAdapterFactory:
    """데이터 출처(source) 기반으로 적절한 어댑터를 선택하는 팩토리.

    Factory 패턴을 사용하여 DataSource enum으로 어댑터를 자동 선택합니다.
    새로운 데이터 출처는 register_adapter()로 동적 등록 가능합니다.

    Example:
        >>> factory = CandleAdapterFactory()
        >>> adapter = factory.get_adapter(DataSource.UPBIT)
        >>> models = adapter.to_candle_models(df, "KRW-BTC", "1m")
    """

    def __init__(self) -> None:
        """기본 어댑터들을 등록하여 팩토리 초기화."""
        self._adapters: dict[DataSource, CandleDataAdapter] = {
            DataSource.UPBIT: UpbitCandleAdapter(),
            DataSource.BINANCE: BinanceCandleAdapter(),
            DataSource.HANTU_D: HantuCandleAdapter(),
            DataSource.HANTU_O: HantuCandleAdapter(),
        }

    def get_adapter(self, source: DataSource) -> CandleDataAdapter:
        """출처에 맞는 어댑터 반환.

        Args:
            source: 데이터 출처 (DataSource enum)

        Returns:
            해당 출처의 CandleDataAdapter 구현체

        Raises:
            ValueError: 알 수 없는 출처인 경우
        """
        adapter = self._adapters.get(source)
        if adapter is None:
            raise ValueError(f"Unknown source: {source}. " f"Available: {list(self._adapters.keys())}")
        return adapter

    def register_adapter(self, source: DataSource, adapter: CandleDataAdapter) -> None:
        """새로운 데이터 출처의 어댑터를 동적으로 등록.

        Args:
            source: 데이터 출처 (DataSource enum)
            adapter: CandleDataAdapter 구현체

        Example:
            >>> custom_adapter = MyCustomAdapter()
            >>> factory.register_adapter(DataSource.UPBIT, custom_adapter)
        """
        self._adapters[source] = adapter
