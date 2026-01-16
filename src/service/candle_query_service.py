"""통합 캔들 조회 서비스."""

from datetime import datetime
from typing import TYPE_CHECKING

from pandera.typing import DataFrame

from src.common.candle_client import CandleClient, CandleInterval
from src.common.candle_schema import CommonCandleSchema
from src.common.data_adapter import DataSource

if TYPE_CHECKING:
    pass


class CandleQueryService:
    """통합 캔들 조회 서비스.

    여러 거래소(Upbit, Binance, Hantu 등)의 캔들 데이터를
    동일한 인터페이스로 조회할 수 있는 통합 서비스입니다.

    DI 컨테이너를 통해 각 거래소별 CandleClient를 주입받아 사용합니다.

    Example:
        >>> from src.common.data_adapter import DataSource
        >>> from src.common.candle_client import CandleInterval
        >>>
        >>> # DI 컨테이너에서 주입받아 사용
        >>> service = CandleQueryService({
        ...     DataSource.UPBIT: upbit_client,
        ...     DataSource.BINANCE: binance_client,
        ... })
        >>> df = service.get_candles(DataSource.UPBIT, "KRW-BTC", CandleInterval.DAY)
    """

    def __init__(self, clients: dict[DataSource, CandleClient]) -> None:
        """CandleQueryService 초기화.

        Args:
            clients: 데이터 소스별 CandleClient 딕셔너리
        """
        self._clients = clients

    def get_candles(
            self,
            source: DataSource,
            symbol: str,
            interval: CandleInterval,
            count: int = 100,
            end_time: datetime | None = None,
    ) -> DataFrame[CommonCandleSchema]:
        """캔들 데이터 조회.

        Args:
            source: 데이터 소스 (DataSource enum)
            symbol: 심볼 (거래소별 형식, 예: "KRW-BTC", "BTCUSDT", "AAPL")
            interval: 캔들 간격 (CandleInterval)
            count: 조회할 캔들 개수 (기본값: 100)
            end_time: 종료 시간 (해당 시간 이전 데이터 조회, UTC)

        Returns:
            표준 캔들 DataFrame[CommonCandleSchema]
            - index: DatetimeIndex (UTC)
            - columns: open, high, low, close, volume

        Raises:
            ValueError: 등록되지 않은 데이터 소스인 경우
        """
        client = self._get_client(source)
        return client.get_candles(
            symbol=symbol,
            interval=interval,
            count=count,
            end_time=end_time,
        )

    def get_supported_intervals(self, source: DataSource) -> list[CandleInterval]:
        """특정 소스에서 지원하는 캔들 간격 목록.

        Args:
            source: 데이터 소스 (DataSource enum)

        Returns:
            지원하는 CandleInterval 목록

        Raises:
            ValueError: 등록되지 않은 데이터 소스인 경우
        """
        client = self._get_client(source)
        return client.supported_intervals

    @property
    def available_sources(self) -> list[DataSource]:
        """등록된 데이터 소스 목록."""
        return list(self._clients.keys())

    def _get_client(self, source: DataSource) -> CandleClient:
        """데이터 소스에 해당하는 클라이언트 반환.

        Args:
            source: 데이터 소스 (DataSource enum)

        Returns:
            CandleClient 인스턴스

        Raises:
            ValueError: 등록되지 않은 데이터 소스인 경우
        """
        client = self._clients.get(source)
        if client is None:
            available = list(self._clients.keys())
            raise ValueError(
                f"등록되지 않은 데이터 소스입니다: {source}. "
                f"사용 가능한 소스: {available}"
            )
        return client
