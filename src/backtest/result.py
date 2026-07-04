"""백테스트 표준 결과 dataclass.

여러 전략의 성과를 동일한 지표로 비교할 수 있도록 표준화된 결과 컨테이너.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass  # noqa: TCH003
from datetime import date, datetime  # noqa: TCH003
import math


@dataclass(frozen=True)
class EquityPoint:
    """자산곡선 1점 (일 단위). return_pct는 초기자본 대비, drawdown_pct는 고점 대비(≤ 0)."""

    date: date
    return_pct: float
    drawdown_pct: float


@dataclass(frozen=True)
class BacktestResult:
    """백테스트 표준화 결과 지표."""

    strategy_name: str
    initial_cash: float
    final_value: float
    total_return_pct: float  # 총수익률 (%)
    cagr_pct: float | None  # 연복리수익률 (%), 계산 불가 시 None. 실제 캘린더 기간(period_days) 기반.
    max_drawdown_pct: float | None  # MDD (%), 계산 불가 시 None
    sharpe_ratio: float | None  # 샤프 비율 (연율화), 계산 불가 시 None
    total_trades: int  # 청산 완료 거래 수
    win_rate_pct: float | None  # 승률 (%), 거래 0건이면 None. 본전 거래(손익=0)는 패배로 집계됨.
    period_days: int | None  # 백테스트 기간 (일수), 계산 불가 시 None
    start_date: date | None = None  # 실제 사용된 데이터 첫 봉 날짜, 산출 불가 시 None
    end_date: date | None = None    # 실제 사용된 데이터 마지막 봉 날짜, 산출 불가 시 None
    equity_curve: list[EquityPoint] | None = None  # 일별 자산곡선 (TimeReturn 기반), 산출 불가 시 None

    def summary(self) -> str:
        """한 줄 요약 문자열 반환."""
        cagr_str = f"{self.cagr_pct:.2f}%" if self.cagr_pct is not None else "N/A"
        sharpe_str = f"{self.sharpe_ratio:.2f}" if self.sharpe_ratio is not None else "N/A"
        win_str = f"{self.win_rate_pct:.1f}%" if self.win_rate_pct is not None else "N/A"
        mdd_str = f"{self.max_drawdown_pct:.2f}%" if self.max_drawdown_pct is not None else "N/A"
        return (
            f"[{self.strategy_name}] "
            f"수익률={self.total_return_pct:.2f}% CAGR={cagr_str} "
            f"MDD={mdd_str} Sharpe={sharpe_str} "
            f"거래={self.total_trades}회 승률={win_str}"
        )

    def to_dict(self) -> dict[str, object]:
        """모든 필드를 dict로 직렬화한다. CSV 내보내기 등에 사용. 시계열(equity_curve)은 제외."""
        d = dataclasses.asdict(self)
        d.pop("equity_curve", None)
        return d


def _compute_cagr(initial: float, final: float, period_days: int | None) -> float | None:
    """실제 캘린더 기간(period_days)을 기반으로 CAGR(%)을 계산한다.

    Args:
        initial: 초기 자산 가치 (> 0 이어야 함)
        final: 최종 자산 가치 (> 0 이어야 함)
        period_days: 첫 봉~마지막 봉 사이의 실제 캘린더 일수. None 또는 0이면 None 반환.

    Returns:
        CAGR (%), 계산 불가 시 None.
    """
    if initial <= 0 or final <= 0 or not period_days or period_days <= 0:
        return None
    years = period_days / 365.25
    if years <= 0:
        return None
    try:
        cagr = (final / initial) ** (1.0 / years) - 1.0
        return cagr * 100.0
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def _compute_total_return_pct(initial: float, final: float) -> float:
    """총수익률(%)을 계산한다."""
    if initial == 0:
        return 0.0
    return (final / initial - 1.0) * 100.0


def build_equity_curve(timereturn_analysis: object) -> list[EquityPoint] | None:
    """TimeReturn(timeframe=Days) 분석 결과로 일별 자산곡선을 만든다. 산출 불가 시 None.

    equity는 일별 수익률의 누적곱, drawdown은 running peak 대비 %(≤ 0).
    TimeReturn 결과(OrderedDict)는 시간 오름차순을 보장한다.
    """
    try:
        items = list(timereturn_analysis.items())  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return None

    curve: list[EquityPoint] = []
    equity = 1.0
    peak = 1.0
    for dt, ret in items:
        try:
            equity *= 1.0 + float(ret)
        except (TypeError, ValueError):
            continue
        peak = max(peak, equity)
        day = dt.date() if isinstance(dt, datetime) else dt
        curve.append(EquityPoint(
            date=day,
            return_pct=(equity - 1.0) * 100.0,
            drawdown_pct=(equity / peak - 1.0) * 100.0,
        ))
    return curve or None


def _safe_max_drawdown(drawdown_analysis: object) -> float | None:
    """DrawDown 분석기 결과에서 MDD(%)를 안전하게 추출한다. 추출 불가 시 None 반환."""
    try:
        return float(drawdown_analysis.max.drawdown)  # type: ignore[union-attr,attr-defined]
    except (AttributeError, TypeError, KeyError):
        return None


def _safe_sharpe(sharpe_analysis: object) -> float | None:
    """SharpeRatio 분석기 결과에서 샤프 비율을 안전하게 추출한다."""
    try:
        val = sharpe_analysis["sharperatio"]  # type: ignore[index]
        if val is None or not math.isfinite(float(val)):
            return None
        return float(val)
    except (KeyError, TypeError, ValueError):
        return None


def _safe_trade_stats(trade_analysis: object) -> tuple[int, float | None]:
    """TradeAnalyzer 결과에서 (closed_trades, win_rate_pct)를 안전하게 추출한다.

    거래가 없으면 win_rate_pct는 None.
    """
    try:
        total_closed = int(trade_analysis.total.closed)  # type: ignore[union-attr,attr-defined]
    except (AttributeError, TypeError, KeyError):
        total_closed = 0

    if total_closed == 0:
        return 0, None

    try:
        won = int(trade_analysis.won.total)  # type: ignore[union-attr,attr-defined]
        win_rate = won / total_closed * 100.0
    except (AttributeError, TypeError, KeyError, ZeroDivisionError):
        win_rate = None

    return total_closed, win_rate
