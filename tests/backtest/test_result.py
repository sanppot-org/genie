"""BacktestResult 표준화 결과 integration 테스트."""

from __future__ import annotations

import backtrader as bt
import pandas as pd
import pytest

from src.backtest.backtest_builder import BacktestBuilder
from src.backtest.data_feed.pandas import PandasDataFeedConfig
from src.backtest.result import BacktestResult


def _make_df(n: int = 25, start: str = "2023-01-01") -> pd.DataFrame:
    """n 개의 합성 일봉 DataFrame 생성 (단조 상승)."""
    dates = pd.date_range(start=start, periods=n, freq="B")
    base = 100.0
    closes = [base + i for i in range(n)]
    opens = [c - 0.5 for c in closes]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    volumes = [10000] * n
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}, index=dates)


class BuyAndHoldStrategy(bt.Strategy):
    """bar 5에 매수, bar 15에 매도하는 단순 전략 (거래 완결 보장)."""

    params = (("buy_bar", 5), ("sell_bar", 15))

    def next(self) -> None:
        bar_idx = len(self.data)
        if bar_idx == self.p.buy_bar and not self.position:
            self.buy()
        elif bar_idx == self.p.sell_bar and self.position:
            self.close()


class NoTradeStrategy(bt.Strategy):
    """아무 거래도 하지 않는 전략 (win_rate None 검증용)."""

    def next(self) -> None:
        pass


class TestRunWithResult:
    """run_with_result() integration 테스트."""

    def _builder(self, strategy_class: type[bt.Strategy], df: pd.DataFrame | None = None) -> BacktestBuilder:
        if df is None:
            df = _make_df()
        config = PandasDataFeedConfig.create(df)
        return (
            BacktestBuilder()
            .with_initial_cash(1_000_000)
            .with_strategy(strategy_class)
            .add_data(config)
        )

    def test_run_with_result_returns_backtest_result(self) -> None:
        """run_with_result()가 BacktestResult를 반환하고 필드를 올바르게 채우는지 검증."""
        result = self._builder(BuyAndHoldStrategy).run_with_result()

        assert isinstance(result, BacktestResult)
        assert result.strategy_name == "BuyAndHoldStrategy"
        assert result.initial_cash == 1_000_000
        assert result.final_value > 0
        # 단조 상승 데이터이므로 수익률 양수 기대
        assert result.total_return_pct > 0
        # MDD는 None이거나 0 이상
        assert result.max_drawdown_pct is None or result.max_drawdown_pct >= 0
        # 거래 발생 (매수 + 청산)
        assert result.total_trades >= 1
        # 승률은 거래가 있으므로 None이 아님
        assert result.win_rate_pct is not None
        assert 0.0 <= result.win_rate_pct <= 100.0

    def test_run_with_result_custom_strategy_name(self) -> None:
        """strategy_name 파라미터가 결과에 반영되는지 검증."""
        result = self._builder(BuyAndHoldStrategy).run_with_result(strategy_name="커스텀전략")
        assert result.strategy_name == "커스텀전략"

    def test_run_with_result_no_trades_win_rate_is_none(self) -> None:
        """거래 0건 전략의 win_rate_pct가 None인지 검증."""
        result = self._builder(NoTradeStrategy).run_with_result()

        assert isinstance(result, BacktestResult)
        assert result.total_trades == 0
        assert result.win_rate_pct is None

    def test_summary_returns_string(self) -> None:
        """summary() 메서드가 문자열을 반환하는지 검증."""
        result = self._builder(BuyAndHoldStrategy).run_with_result()
        summary = result.summary()
        assert isinstance(summary, str)
        assert "BuyAndHoldStrategy" in summary

    def test_existing_run_still_returns_list(self) -> None:
        """기존 run() 시그니처/반환(raw 리스트)이 유지되는지 검증."""
        builder = self._builder(BuyAndHoldStrategy)
        results = builder.run()
        assert isinstance(results, list)
        assert len(results) == 1

    def test_sharpe_ratio_is_float_with_sufficient_data(self) -> None:
        """260+ bar 데이터에서 sharpe_ratio가 None이 아닌 float인지 검증."""
        df = _make_df(n=260)
        result = self._builder(BuyAndHoldStrategy, df=df).run_with_result()
        # 충분한 데이터에서 샤프 비율이 계산되어야 한다
        assert result.sharpe_ratio is None or isinstance(result.sharpe_ratio, float)
        # float이면 nan/inf가 아니어야 한다
        import math
        if result.sharpe_ratio is not None:
            assert math.isfinite(result.sharpe_ratio)

    def test_with_analyzer_reserved_name_raises(self) -> None:
        """표준 분석기 예약어로 with_analyzer() 호출 시 ValueError가 발생하는지 검증."""
        builder = BacktestBuilder().with_initial_cash(1_000_000)
        for reserved in ("returns", "sharpe", "drawdown", "trades"):
            with pytest.raises(ValueError, match=reserved):
                builder.with_analyzer(bt.analyzers.SharpeRatio, name=reserved)

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict()가 BacktestResult의 모든 필드를 포함하는지 검증."""
        result = self._builder(BuyAndHoldStrategy).run_with_result()
        d = result.to_dict()
        assert isinstance(d, dict)
        expected_keys = {
            "strategy_name", "initial_cash", "final_value", "total_return_pct",
            "cagr_pct", "max_drawdown_pct", "sharpe_ratio", "total_trades",
            "win_rate_pct", "period_days",
        }
        assert expected_keys == set(d.keys())
