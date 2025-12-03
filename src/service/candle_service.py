"""Candle data service for saving candle data to database."""

from typing import TYPE_CHECKING

from src.common.data_adapter import DataSource

if TYPE_CHECKING:
    import pandas as pd

    from src.adapters.adapter_factory import CandleAdapterFactory
    from src.database.repositories import CandleDailyRepository, CandleMinute1Repository


class CandleService:
    """캔들 데이터 저장 서비스.

    데이터 출처(source)에 맞는 어댑터를 자동 선택하여
    Raw DataFrame을 정규화하고 DB에 저장합니다.

    주요 기능:
    - 어댑터 자동 선택 (Factory 패턴)
    - API CandleInterval → DB interval 변환
    - interval별 적절한 repository 선택
    - Bulk Insert (Upsert)
    """

    def __init__(
            self,
            minute1_repository: "CandleMinute1Repository",
            daily_repository: "CandleDailyRepository",
            adapter_factory: "CandleAdapterFactory",
    ) -> None:
        """CandleService 초기화.

        Args:
            minute1_repository: 1분봉 캔들 데이터 저장소
            daily_repository: 일봉 캔들 데이터 저장소
            adapter_factory: 어댑터 팩토리
        """
        self._minute1_repo = minute1_repository
        self._daily_repo = daily_repository
        self._factory = adapter_factory

    def save_candles(
            self,
            df: "pd.DataFrame",
            source: DataSource,
            ticker: str,
            interval: object,
    ) -> None:
        """Raw DataFrame을 정규화하여 DB에 저장.

        Args:
            df: 출처의 원본 DataFrame (컬럼명, 타임존 등이 출처마다 다를 수 있음)
            source: 데이터 출처 (DataSource enum)
            ticker: 종목 코드 (예: "KRW-BTC", "BTCUSDT", "005930")
            interval: 출처별 interval 타입
                - Upbit: UpbitCandleInterval
                - Binance: BinanceCandleInterval
                - Hantu: OverseasMinuteInterval | OverseasCandlePeriod

        Raises:
            ValueError: 알 수 없는 source 또는 지원하지 않는 interval인 경우

        Example:
            >>> from src.common.data_adapter import DataSource
            >>> from src.upbit.upbit_api import UpbitCandleInterval
            >>> service = CandleService(minute1_repo, daily_repo, factory)
            >>> df = upbit_api.get_candles(interval=UpbitCandleInterval.MINUTE_1)
            >>> service.save_candles(
            ...     df=df,
            ...     source=DataSource.UPBIT,
            ...     ticker="KRW-BTC",
            ...     interval=UpbitCandleInterval.MINUTE_1
            ... )
            >>> print("캔들 저장 완료")
        """
        from src.database.models import CandleMinute1

        adapter = self._factory.get_adapter(source)
        candle_models = adapter.to_candle_models(df, ticker, interval)

        if not candle_models:
            return

        if isinstance(candle_models[0], CandleMinute1):
            self._minute1_repo.bulk_upsert(candle_models)  # type: ignore[arg-type]
        else:
            self._daily_repo.bulk_upsert(candle_models)  # type: ignore[arg-type]
