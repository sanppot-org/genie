"""미국 주식 일봉 조회 클라이언트 (FDR 주 소스 → yfinance 폴백).

FDR `DataReader`와 yfinance `history(auto_adjust=False)`는 둘 다
원주가 OHLCV + `Adj Close`를 한 번에 반환한다(종목당 1콜로 전체 히스토리).
FDR을 1순위로 둔다: naive date 인덱스(타임존 처리 불필요), 국내 친화.
FDR 실패/빈 응답 시 yfinance로 폴백한다. 둘 다 비면 빈 리스트.
"""

from dataclasses import dataclass
from datetime import date
import logging

import FinanceDataReader as fdr  # noqa: N813
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsDailyBar:
    """미국 주식 일봉 1행 (원주가 OHLCV + 수정 종가)."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float


class UsStockDailyClient:
    """FDR 주 소스 + yfinance 폴백 일봉 클라이언트."""

    def fetch(self, symbol: str, start: date, end: date | None = None) -> list[UsDailyBar]:
        """심볼의 일봉을 [start, end]로 조회. 실패 시 폴백, 데이터 없으면 빈 리스트."""
        df = self._try_fdr(symbol, start, end)
        if df is None or df.empty:
            df = self._try_yfinance(symbol, start, end)
        if df is None or df.empty:
            logger.warning("US 일봉 데이터 없음 symbol=%s", symbol)
            return []
        return self._normalize(df)

    def _try_fdr(self, symbol: str, start: date, end: date | None) -> pd.DataFrame | None:
        try:
            result: pd.DataFrame = fdr.DataReader(symbol, start, end)
            return result
        except Exception:
            logger.exception("FDR 조회 실패 symbol=%s → yfinance 폴백", symbol)
            return None

    def _try_yfinance(self, symbol: str, start: date, end: date | None) -> pd.DataFrame | None:
        try:
            result: pd.DataFrame = yf.Ticker(symbol).history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d") if end else None,
                auto_adjust=False,
            )
            return result
        except Exception:
            logger.exception("yfinance 조회 실패 symbol=%s", symbol)
            return None

    def _normalize(self, df: pd.DataFrame) -> list[UsDailyBar]:
        """OHLCV + Adj Close DataFrame을 UsDailyBar 리스트로 변환 (Adj Close 없으면 Close 사용)."""
        bars: list[UsDailyBar] = []
        for idx, row in df.iterrows():
            close = float(row["Close"])
            adj = float(row["Adj Close"]) if "Adj Close" in df.columns and pd.notna(row["Adj Close"]) else close
            bars.append(UsDailyBar(
                date=pd.Timestamp(str(idx)).date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=close,
                volume=int(row["Volume"]),
                adj_close=adj,
            ))
        return bars
