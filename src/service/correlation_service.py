"""멀티 티커 상관관계 분석 서비스.

세션 수명:
    캔들 로드만 session_scope 안에서 수행하고, 정렬·수익률·상관 계산은
    세션 종료 후 수행한다(커넥션 누수 방지). BacktestService와 동일 패턴.
    이 레포는 QueuePool 고갈 이력이 있으므로 이 패턴은 필수다.

설계 결정(1차 릴리스):
    - 기본은 수익률(pct_change) 상관. 가격 시계열은 비정상(추세 보유)이라
      가격 레벨 상관은 허위로 높게 나오므로 차분(수익률)으로 추세를 제거한다.
    - 결측 처리는 dropna(보수적). 공통 거래일만 사용한다.
    - 단일 자산군만 한 요청에 허용(호출부에서 보장). 롤링·가격상관은 후속.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import logging
from typing import TYPE_CHECKING, Literal, cast

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.database.database import Database

logger = logging.getLogger(__name__)

# 통계적으로 신뢰할 만한 상관계수의 최소 관측 수. 미만이면 경고만 추가.
_MIN_OBSERVATIONS: int = 30

_VALID_METHODS = ("pearson", "spearman")
_VALID_RETURN_TYPES = ("returns", "price")


@dataclass(frozen=True)
class CorrelationOutput:
    """상관관계 계산 결과.

    matrix[i][j]는 tickers[i]와 tickers[j]의 상관계수. 대각은 1.0.
    계산 불가(분산 0 등)인 셀은 None.
    """

    tickers: list[str]                  # 행/열 순서 (정렬 후 최종 포함 티커)
    matrix: list[list[float | None]]    # N×N
    observations: int                   # 정렬·dropna 후 공통 관측 수
    period_start: date | None
    period_end: date | None
    method: str
    return_type: str
    dropped: list[str]                  # 데이터 없어 제외된 티커
    warnings: list[str]


def compute_correlation(
    close_by_ticker: dict[str, pd.Series],
    method: str = "pearson",
    return_type: str = "returns",
) -> CorrelationOutput:
    """티커별 종가 시계열로 상관행렬을 계산하는 순수 함수.

    Args:
        close_by_ticker: {ticker: close Series}. Series는 DatetimeIndex 또는
            date 인덱스를 가진 종가. 입력 순서가 결과 행/열 순서를 결정한다.
        method: "pearson"(기본) 또는 "spearman".
        return_type: "returns"(기본, pct_change 후 상관) 또는 "price"(원시 가격 상관).

    Returns:
        CorrelationOutput. 빈/전부 NaN인 티커는 dropped로 분리한다.

    Raises:
        ValueError: method / return_type 가 허용값이 아닐 때.
    """
    if method not in _VALID_METHODS:
        raise ValueError(f"지원하지 않는 method: {method!r} ({_VALID_METHODS} 중 하나)")
    if return_type not in _VALID_RETURN_TYPES:
        raise ValueError(f"지원하지 않는 return_type: {return_type!r} ({_VALID_RETURN_TYPES} 중 하나)")

    warnings: list[str] = []

    # 1) 빈/전부 NaN 시계열은 제외하고, 각 시계열을 자정 정렬·정렬·중복제거로 정규화.
    #    입력은 일봉 전제. 일중(intraday) 인덱스를 넣으면 normalize가 같은 날로 뭉개고
    #    keep="last"가 앞 바를 버리므로 호출부가 일봉만 넣어야 한다.
    usable: dict[str, pd.Series] = {}
    dropped: list[str] = []
    for ticker, series in close_by_ticker.items():
        if series is None or series.dropna().empty:
            dropped.append(ticker)
            continue
        s = series.dropna().copy()
        s.index = pd.to_datetime(s.index).normalize()
        s = s.sort_index()
        s = s[~s.index.duplicated(keep="last")]
        usable[ticker] = s

    tickers = list(usable.keys())

    if len(tickers) < 2:
        warnings.append(f"상관계산에 필요한 유효 티커가 부족합니다(유효 {len(tickers)}개, 최소 2개).")
        return CorrelationOutput(
            tickers=tickers,
            matrix=_identity_matrix(len(tickers)),
            observations=0,
            period_start=None,
            period_end=None,
            method=method,
            return_type=return_type,
            dropped=dropped,
            warnings=warnings,
        )

    # 2) 수익률 상관이면 각 티커의 native 시계열에서 먼저 pct_change를 계산한다.
    #    (정렬 후 pct_change를 하면 한 티커의 결측이 전 티커의 수익률을 다일 합성하므로
    #     순서를 native → 정렬로 둔다.) 0가격(거래정지/오류)에서 생기는 ±inf는
    #    유효 관측이 아니므로 NaN으로 치환해 dropna가 제거하도록 한다.
    series_for_corr: dict[str, pd.Series] = {}
    for ticker, s in usable.items():
        if return_type == "returns":
            r = s.pct_change().replace([np.inf, -np.inf], np.nan)
            series_for_corr[ticker] = r
        else:
            series_for_corr[ticker] = s

    # 3) outer 결합 후 공통 관측만 남긴다(dropna).
    frame = pd.concat(series_for_corr, axis=1)
    aligned = frame.dropna(how="any")

    observations = len(aligned)
    if observations < 2:
        warnings.append(f"공통 관측 수가 부족합니다(observations={observations}). 기간이 겹치는지 확인하세요.")
        return CorrelationOutput(
            tickers=tickers,
            matrix=_identity_matrix(len(tickers)),
            observations=observations,
            period_start=None,
            period_end=None,
            method=method,
            return_type=return_type,
            dropped=dropped,
            warnings=warnings,
        )

    if observations < _MIN_OBSERVATIONS:
        warnings.append(f"관측 수가 적어({observations} < {_MIN_OBSERVATIONS}) 상관계수 신뢰도가 낮을 수 있습니다.")

    corr = aligned.corr(method=cast("Literal['pearson', 'kendall', 'spearman']", method))
    # tickers 순서로 행/열 재정렬(concat이 순서를 보존하지만 명시적으로 고정).
    corr = corr.reindex(index=tickers, columns=tickers)

    matrix: list[list[float | None]] = [
        [None if pd.isna(v) else float(v) for v in row]
        for row in corr.to_numpy()
    ]
    # 대각은 정의상 자기상관 1.0. 분산 0 시계열은 pandas가 대각도 NaN으로 주므로 강제한다.
    off_diagonal_nan = False
    for i in range(len(tickers)):
        for j in range(len(tickers)):
            if i == j:
                matrix[i][j] = 1.0
            elif matrix[i][j] is None:
                off_diagonal_nan = True
    if off_diagonal_nan:
        warnings.append("일부 페어의 상관계수를 계산할 수 없습니다(분산 0 또는 데이터 부족).")

    period_index = aligned.index
    period_start = period_index.min().date()
    period_end = period_index.max().date()

    return CorrelationOutput(
        tickers=tickers,
        matrix=matrix,
        observations=observations,
        period_start=period_start,
        period_end=period_end,
        method=method,
        return_type=return_type,
        dropped=dropped,
        warnings=warnings,
    )


def _identity_matrix(n: int) -> list[list[float | None]]:
    """n×n 단위행렬(대각 1.0, 그 외 None). 계산 불가 분기의 일관된 출력용."""
    return [[1.0 if i == j else None for j in range(n)] for i in range(n)]


class CorrelationService:
    """티커 조회 → 종가 로드(세션 안) → 상관 계산(세션 밖) 오케스트레이션.

    BacktestService와 동일하게 캔들 로드만 session_scope 안에서 수행하고,
    정렬·수익률·상관 계산은 세션 종료 후 compute_correlation으로 위임한다.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def run(
        self,
        tickers: list[str],
        start: date | None = None,
        end: date | None = None,
        asset: str = "stock",
        method: str = "pearson",
        return_type: str = "returns",
    ) -> CorrelationOutput:
        """티커 목록의 일봉 종가로 상관행렬 계산.

        Args:
            tickers: 종목 코드 목록(입력 순서가 결과 행/열 순서를 결정).
            start: 시작일(None이면 전체).
            end: 종료일(None이면 전체).
            asset: "stock"만 지원(1차 릴리스). crypto는 후속.
            method: "pearson"(기본) 또는 "spearman".
            return_type: "returns"(기본) 또는 "price".

        Returns:
            CorrelationOutput. 미등록·무데이터 티커는 dropped로 분리.

        Raises:
            ValueError: asset 미지원 시.
        """
        if asset != "stock":
            raise ValueError(f"현재 asset={asset!r}는 미지원입니다. 1차 릴리스는 stock(일봉)만 지원합니다.")

        # ── 세션 안: 티커 resolve + 멀티 로드 + 종가 시계열 추출 ──────────────
        close_by_ticker: dict[str, pd.Series] = {}
        unresolved: list[str] = []  # 미등록 + 무데이터
        with self._database.session_scope() as session:
            from src.backtest.data_feed.candle_loader import stock_daily_candles_to_dataframe
            from src.database.stock_daily_candle_repository import StockDailyCandleRepository
            from src.database.ticker_repository import TickerRepository

            ticker_repo = TickerRepository(session)
            id_by_ticker: dict[str, int] = {}
            for name in tickers:
                obj = ticker_repo.find_by_ticker(name)
                if obj is None or obj.id is None:
                    unresolved.append(name)
                else:
                    id_by_ticker[name] = obj.id

            rows_by_id = StockDailyCandleRepository(session).find_by_tickers(
                list(id_by_ticker.values()), start, end,
            )
            for name, ticker_id in id_by_ticker.items():
                rows = rows_by_id.get(ticker_id, [])
                if not rows:
                    unresolved.append(name)
                    continue
                df, _ = stock_daily_candles_to_dataframe(rows)
                close_by_ticker[name] = df["close"]

        # ── 세션 종료 후: 순수 계산 ───────────────────────────────────────
        output = compute_correlation(close_by_ticker, method=method, return_type=return_type)

        if unresolved:
            merged_dropped = unresolved + [d for d in output.dropped if d not in unresolved]
            output = replace(output, dropped=merged_dropped)
        return output
