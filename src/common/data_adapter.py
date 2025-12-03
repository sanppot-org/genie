"""Data adapter interfaces for candle data normalization."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from src.database.models import CandleBase


class DataSource(str, Enum):
    """데이터 출처 enum.

    각 데이터 소스를 타입 안전하게 표현합니다.
    문자열과 호환 가능하도록 str을 상속받습니다.
    """

    UPBIT = "upbit"
    BINANCE = "binance"
    HANTU = "hantu"


class CandleDataAdapter(ABC):
    """캔들 데이터 어댑터 인터페이스.

    각 데이터 출처(Upbit, Binance, Hantu 등)의 Raw DataFrame을
    캔들 ORM 모델 리스트로 변환하는 책임을 가집니다.

    주요 역할:
    - 컬럼명 정규화 (출처별 다른 컬럼명 → 표준 필드명)
    - 타임존 정규화 (KST/EST 등 → UTC)
    - 데이터 타입 변환
    - ORM 모델 생성 (CandleMinute1 또는 CandleDaily)
    """

    @abstractmethod
    def to_candle_models(
            self, df: "pd.DataFrame", ticker: str, interval: object
    ) -> Sequence["CandleBase"]:
        """Raw DataFrame을 캔들 모델 리스트로 변환.

        각 어댑터는 출처별 interval 타입을 받아서:
        1. interval에 따라 CandleMinute1 또는 CandleDaily 선택
        2. DataFrame → 캔들 모델 변환

        Args:
            df: 출처에서 받은 원본 DataFrame
            ticker: 종목 코드 (예: "KRW-BTC", "BTCUSDT")
            interval: 출처별 interval 타입
                - Upbit: UpbitCandleInterval
                - Binance: BinanceCandleInterval
                - Hantu: OverseasMinuteInterval | OverseasCandlePeriod

        Returns:
            캔들 모델 리스트 (CandleMinute1 또는 CandleDaily, timestamp는 UTC로 정규화됨)
        """
        pass
