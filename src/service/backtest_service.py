"""백테스트 서비스 — 티커 조회·캔들 로드·전략 실행 코어.

scripts/backtest.py의 CLI와 API 라우터가 공통으로 사용하는 코어 로직.

세션 수명:
    캔들 로드·DataFrame 변환만 session_scope 안에서 수행하고,
    backtrader 실행은 세션 종료 후 수행한다(커넥션 누수 방지).
    이 레포는 QueuePool 고갈 이력이 있으므로 이 패턴은 필수다.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import date, datetime
import io
import logging

import pandas as pd

from src.backtest.cli import is_bust, merge_params
from src.backtest.registry import StrategySpec, get_strategy, list_strategies
from src.backtest.result import BacktestResult
from src.database.database import Database

logger = logging.getLogger(__name__)

_DEFAULT_PERCENT: int = 95


@dataclass
class BacktestRunResult:
    """단일 전략 백테스트 결과 + bust 판정."""

    result: BacktestResult
    bust: bool
    timeframe: str


@dataclass(frozen=True)
class BacktestRunOutput:
    """BacktestService.run() 전체 실행 결과."""

    results: list[BacktestRunResult]
    skipped: list[str]       # 캔들 데이터 없어 제외된 전략명
    failed: list[str]        # 실행 예외로 실패한 전략명
    mixed_timeframes: bool   # 결과 전략들의 타임프레임이 혼합되어 있으면 True


class BacktestService:
    """티커 조회 → 캔들 로드(세션 안) → 백테스트 실행(세션 밖) 오케스트레이션."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def list_strategies(self) -> list[StrategySpec]:
        """레지스트리에 등록된 전략 목록 반환."""
        return [get_strategy(name) for name in list_strategies()]

    def run(
        self,
        ticker: str,
        strategy_names: list[str],
        start: date | None,
        end: date | None,
        initial_cash: float,
        commission: float,
        slippage: float,
        asset: str = "stock",
        param_overrides: dict[str, object] | None = None,
    ) -> BacktestRunOutput:
        """전략 목록을 동일 조건으로 실행하여 결과 반환.

        Args:
            ticker: 종목 코드
            strategy_names: 전략 이름 목록
            start: 시작일 (None이면 전체)
            end: 종료일 (None이면 전체)
            initial_cash: 초기 자본
            commission: 수수료율
            slippage: 슬리피지율
            asset: "stock" 또는 "crypto"
            param_overrides: 파라미터 override (단일 전략에만 적용 권장)

        Returns:
            BacktestRunOutput. skipped = 캔들 없는 전략, failed = 실행 예외 전략.
        """
        if asset not in ("stock", "crypto"):
            raise ValueError(f"지원하지 않는 asset: {asset!r} (stock 또는 crypto만 허용)")

        overrides = param_overrides or {}
        specs = [get_strategy(name) for name in strategy_names]

        start_dt = datetime(start.year, start.month, start.day) if start else None
        end_dt = datetime(end.year, end.month, end.day) if end else None

        # ── 1단계: 세션 안에서 캔들 로드 ──────────────────────────────────
        # 티커 조회는 별도 세션으로 먼저 수행한다.
        spec_dfs: dict[str, pd.DataFrame] = {}
        skipped: list[str] = []
        with self._database.session_scope() as session:
            from src.database.ticker_repository import TickerRepository
            ticker_obj = TickerRepository(session).find_by_ticker(ticker)
            if ticker_obj is None or ticker_obj.id is None:
                raise ValueError(f"티커 미등록: {ticker}")
            ticker_id: int = ticker_obj.id

        # 전략별로 독립 세션을 열어 캔들을 로드한다.
        # DB 예외(테이블 없음 등)가 발생하면 해당 세션만 롤백·종료되고
        # 다음 전략은 새 세션으로 안전하게 시도할 수 있다.
        for spec in specs:
            try:
                with self._database.session_scope() as session:
                    df, _ = _load_candles_df(spec, ticker_id, start_dt, end_dt, asset, session)
                if not df.empty:
                    spec_dfs[spec.name] = df
                else:
                    logger.warning("[%s] 캔들 데이터 없음 (ticker=%s) — 스킵", spec.name, ticker)
                    skipped.append(spec.name)
            except Exception as exc:
                logger.warning(
                    "[%s] 캔들 로드 실패 (ticker=%s, timeframe=%s) — 스킵: %s",
                    spec.name,
                    ticker,
                    spec.timeframe,
                    exc,
                )
                skipped.append(spec.name)

        # ── 2단계: 세션 종료 후 백테스트 실행 ────────────────────────────
        results: list[BacktestRunResult] = []
        failed: list[str] = []
        for spec in specs:
            spec_df: pd.DataFrame | None = spec_dfs.get(spec.name)
            if spec_df is None:
                continue
            bt_result = _run_single_strategy(
                spec=spec,
                ticker=ticker,
                df=spec_df,
                initial_cash=initial_cash,
                commission=commission,
                slippage=slippage,
                param_overrides=overrides,
            )
            if bt_result is not None:
                results.append(BacktestRunResult(
                    result=bt_result,
                    bust=is_bust(bt_result.final_value, bt_result.total_return_pct),
                    timeframe=spec.timeframe,
                ))
            else:
                failed.append(spec.name)

        timeframes_used = {r.timeframe for r in results}
        return BacktestRunOutput(
            results=results,
            skipped=skipped,
            failed=failed,
            mixed_timeframes=len(timeframes_used) > 1,
        )


# ---------------------------------------------------------------------------
# 내부 헬퍼 — scripts/backtest.py의 동일 함수와 동형, 재사용 가능하도록 분리
# ---------------------------------------------------------------------------

def _load_candles_df(
    spec: StrategySpec,
    ticker_id: int,
    start_dt: datetime | None,
    end_dt: datetime | None,
    asset: str,
    session: object,
) -> tuple[pd.DataFrame, str]:
    """spec.timeframe + asset 조합에 맞는 리포지토리로 캔들 로드 → DataFrame 반환.

    세션 안에서 호출해야 한다.
    """
    from src.backtest.data_feed.candle_loader import candles_to_dataframe, stock_daily_candles_to_dataframe
    from src.database.candle_repositories import CandleDailyRepository, CandleHour1Repository, CandleMinute1Repository

    if spec.timeframe == "1d" and asset == "stock":
        from datetime import date as date_type

        from src.database.stock_daily_candle_repository import StockDailyCandleRepository
        from_date: date_type | None = start_dt.date() if start_dt else None
        to_date: date_type | None = end_dt.date() if end_dt else None
        rows = StockDailyCandleRepository(session).find_by_ticker(ticker_id, from_date, to_date)  # type: ignore[arg-type]
        df, _ = stock_daily_candles_to_dataframe(rows)
        return df, "1d"

    if spec.timeframe == "1d":
        repo: CandleDailyRepository | CandleHour1Repository | CandleMinute1Repository = CandleDailyRepository(session)  # type: ignore[arg-type]
    elif spec.timeframe == "1h":
        repo = CandleHour1Repository(session)  # type: ignore[arg-type]
    elif spec.timeframe == "1m":
        repo = CandleMinute1Repository(session)  # type: ignore[arg-type]
    else:
        logger.warning("[%s] 지원하지 않는 타임프레임: %s — 스킵", spec.name, spec.timeframe)
        return pd.DataFrame(), "unknown"

    adjusted_end = end_dt
    if end_dt is not None and spec.timeframe in ("1h", "1m"):
        adjusted_end = end_dt.replace(hour=23, minute=59, second=59)

    candles = repo.get_candles(ticker_id, start_dt, adjusted_end)  # type: ignore[return-value]
    if not candles:
        return pd.DataFrame(), spec.timeframe

    df, actual_tf = candles_to_dataframe(candles)  # type: ignore[arg-type]
    return df, actual_tf


def _run_single_strategy(
    spec: StrategySpec,
    ticker: str,
    df: pd.DataFrame,
    initial_cash: float,
    commission: float,
    slippage: float,
    param_overrides: dict[str, object],
    verbose: bool = False,
) -> BacktestResult | None:
    """단일 전략 백테스트 실행. 실패 시 None 반환."""
    from src.backtest.backtest_builder import BacktestBuilder
    from src.backtest.commission_config import CommissionConfig
    from src.backtest.data_feed.pandas import PandasDataFeedConfig

    if df.empty:
        return None

    final_params = merge_params(spec.default_params, param_overrides)
    data_config = PandasDataFeedConfig.create(df, name=f"{ticker}_{spec.timeframe}")

    builder = (
        BacktestBuilder()
        .with_initial_cash(initial_cash)
        .with_commission(CommissionConfig.stock(commission))
        .with_slippage(slippage)
        .with_strategy(spec.strategy_class, **final_params)
        .add_data(data_config)
    )

    if not spec.manages_own_sizing:
        sizer_cfg = spec.default_sizer
        if sizer_cfg is None:
            from src.backtest.sizer_config import SizerConfig
            sizer_cfg = SizerConfig.percent(_DEFAULT_PERCENT)
        builder = builder.with_sizer(sizer_cfg)

    if spec.requires_cheat_on_open:
        builder = builder.with_cheat_on_open(True)

    try:
        if verbose:
            return builder.run_with_result(strategy_name=spec.name)
        with contextlib.redirect_stdout(io.StringIO()):
            return builder.run_with_result(strategy_name=spec.name)
    except Exception as exc:
        logger.error("[%s] 백테스트 실행 실패: %s", spec.name, exc, exc_info=True)
        return None
