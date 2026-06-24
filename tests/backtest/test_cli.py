"""src/backtest/cli.py 단위 테스트 — DB 없이 순수 함수 검증."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.backtest.cli import (
    ComparisonRow,
    derive_sizer_label,
    format_comparison_table,
    is_bust,
    merge_params,
    parse_param_override,
    parse_param_overrides,
    results_to_csv_str,
)
from src.backtest.data_feed.candle_loader import stock_daily_candles_to_dataframe
from src.backtest.result import BacktestResult
from src.backtest.sizer_config import SizerConfig

# ---------------------------------------------------------------------------
# parse_param_override
# ---------------------------------------------------------------------------

class TestParseParamOverride:
    def test_float(self) -> None:
        key, val = parse_param_override("k_value=0.5")
        assert key == "k_value"
        assert val == 0.5
        assert isinstance(val, float)

    def test_int(self) -> None:
        key, val = parse_param_override("ma_period=20")
        assert key == "ma_period"
        assert val == 20
        assert isinstance(val, int)

    def test_bool_true(self) -> None:
        key, val = parse_param_override("enable_long=True")
        assert key == "enable_long"
        assert val is True

    def test_bool_false(self) -> None:
        key, val = parse_param_override("enable_short=False")
        assert key == "enable_short"
        assert val is False

    def test_tuple(self) -> None:
        key, val = parse_param_override("ema_periods=(5,20,40)")
        assert key == "ema_periods"
        assert val == (5, 20, 40)
        assert isinstance(val, tuple)

    def test_string_fallback(self) -> None:
        key, val = parse_param_override("name=hello world")
        assert key == "name"
        assert val == "hello world"

    def test_missing_equals_raises(self) -> None:
        with pytest.raises(ValueError, match="="):
            parse_param_override("k_value_only")

    def test_empty_key_raises(self) -> None:
        """key가 비어있으면 ValueError."""
        with pytest.raises(ValueError, match="key가 비어있습니다"):
            parse_param_override("=1")

    def test_value_with_equals_sign(self) -> None:
        """값 자체에 = 가 포함된 경우 첫 = 만 구분자로 사용."""
        key, val = parse_param_override("label=a=b")
        assert key == "label"
        assert val == "a=b"

    def test_whitespace_stripped(self) -> None:
        key, val = parse_param_override("  k_value  =  0.3  ")
        assert key == "k_value"
        assert val == pytest.approx(0.3)


class TestParseParamOverrides:
    def test_multiple(self) -> None:
        result = parse_param_overrides(["k_value=0.3", "ma_period=10"])
        assert result == {"k_value": 0.3, "ma_period": 10}

    def test_empty(self) -> None:
        assert parse_param_overrides([]) == {}

    def test_last_wins_on_duplicate(self) -> None:
        result = parse_param_overrides(["k_value=0.3", "k_value=0.7"])
        assert result["k_value"] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# merge_params
# ---------------------------------------------------------------------------

class TestMergeParams:
    def test_override_replaces(self) -> None:
        merged = merge_params({"k_value": 0.5, "ma_period": 15}, {"k_value": 0.3})
        assert merged["k_value"] == pytest.approx(0.3)
        assert merged["ma_period"] == 15

    def test_extra_key_allowed(self) -> None:
        merged = merge_params({"k_value": 0.5}, {"new_key": 99})
        assert merged["new_key"] == 99
        assert merged["k_value"] == pytest.approx(0.5)

    def test_does_not_mutate_original(self) -> None:
        original = {"k_value": 0.5}
        merge_params(original, {"k_value": 0.9})
        assert original["k_value"] == pytest.approx(0.5)

    def test_empty_override(self) -> None:
        merged = merge_params({"k_value": 0.5}, {})
        assert merged == {"k_value": 0.5}


# ---------------------------------------------------------------------------
# derive_sizer_label
# ---------------------------------------------------------------------------

class TestDeriveSizerLabel:
    def test_manages_own_sizing(self) -> None:
        assert derive_sizer_label(None, manages_own_sizing=True, default_cli_percent=95) == "self-managed"

    def test_none_sizer_uses_default_percent(self) -> None:
        label = derive_sizer_label(None, manages_own_sizing=False, default_cli_percent=95)
        assert label == "percent(95)"

    def test_percent_sizer(self) -> None:
        cfg = SizerConfig.percent(99)
        label = derive_sizer_label(cfg, manages_own_sizing=False, default_cli_percent=95)
        assert label == "percent(99)"

    def test_all_in_sizer(self) -> None:
        cfg = SizerConfig.all_in()
        label = derive_sizer_label(cfg, manages_own_sizing=False, default_cli_percent=95)
        assert label == "all-in"

    def test_fixed_sizer(self) -> None:
        cfg = SizerConfig.fixed(100)
        label = derive_sizer_label(cfg, manages_own_sizing=False, default_cli_percent=95)
        assert label == "fixed(100)"


# ---------------------------------------------------------------------------
# stock_daily_candles_to_dataframe (수정주가 적용)
# ---------------------------------------------------------------------------

def _make_stock_row(
    d: date,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int,
    adj_open: float | None = None,
    adj_high: float | None = None,
    adj_low: float | None = None,
    adj_close: float | None = None,
) -> MagicMock:
    row = MagicMock()
    row.date = d
    row.open = open_
    row.high = high
    row.low = low
    row.close = close
    row.volume = volume
    row.adj_open = adj_open
    row.adj_high = adj_high
    row.adj_low = adj_low
    row.adj_close = adj_close
    return row


class TestStockDailyCandlesToDataframe:
    def test_empty_returns_empty_df(self) -> None:
        df, tf = stock_daily_candles_to_dataframe([])
        assert df.empty
        assert tf == "1d"

    def test_all_adj_columns_used_directly(self) -> None:
        row = _make_stock_row(
            date(2024, 1, 2), 100.0, 110.0, 90.0, 105.0, 1000,
            adj_open=50.0, adj_high=55.0, adj_low=45.0, adj_close=52.5,
        )
        df, tf = stock_daily_candles_to_dataframe([row])
        assert tf == "1d"
        assert df.iloc[0]["open"] == pytest.approx(50.0)
        assert df.iloc[0]["high"] == pytest.approx(55.0)
        assert df.iloc[0]["low"] == pytest.approx(45.0)
        assert df.iloc[0]["close"] == pytest.approx(52.5)
        assert df.iloc[0]["volume"] == 1000

    def test_ratio_adjustment_when_partial_adj(self) -> None:
        """adj_close만 있을 때 수정계수(adj_close/close)로 open/high/low 조정."""
        row = _make_stock_row(
            date(2024, 1, 3), 100.0, 120.0, 80.0, 100.0, 500,
            adj_close=50.0,  # 계수 = 0.5
        )
        df, _ = stock_daily_candles_to_dataframe([row])
        assert df.iloc[0]["open"] == pytest.approx(50.0)   # 100 * 0.5
        assert df.iloc[0]["high"] == pytest.approx(60.0)   # 120 * 0.5
        assert df.iloc[0]["low"] == pytest.approx(40.0)    # 80 * 0.5
        assert df.iloc[0]["close"] == pytest.approx(50.0)
        assert df.iloc[0]["volume"] == 500  # volume 그대로

    def test_raw_fallback_when_no_adj(self) -> None:
        """adj 없으면 raw 값 사용."""
        row = _make_stock_row(date(2024, 1, 4), 200.0, 210.0, 190.0, 205.0, 300)
        df, _ = stock_daily_candles_to_dataframe([row])
        assert df.iloc[0]["open"] == pytest.approx(200.0)
        assert df.iloc[0]["close"] == pytest.approx(205.0)

    def test_sorted_by_date(self) -> None:
        rows = [
            _make_stock_row(date(2024, 1, 5), 100.0, 105.0, 95.0, 102.0, 100),
            _make_stock_row(date(2024, 1, 3), 98.0, 103.0, 93.0, 100.0, 120),
        ]
        df, _ = stock_daily_candles_to_dataframe(rows)
        assert df.index[0] < df.index[1]

    def test_timeframe_is_1d(self) -> None:
        row = _make_stock_row(date(2024, 1, 6), 100.0, 105.0, 95.0, 102.0, 100)
        _, tf = stock_daily_candles_to_dataframe([row])
        assert tf == "1d"


# ---------------------------------------------------------------------------
# format_comparison_table
# ---------------------------------------------------------------------------

def _make_result(name: str, ret: float, cagr: float | None = None, timeframe: str = "1d", sizer: str = "percent(95)") -> tuple[BacktestResult, ComparisonRow]:
    r = BacktestResult(
        strategy_name=name,
        initial_cash=10_000_000.0,
        final_value=10_000_000.0 * (1 + ret / 100),
        total_return_pct=ret,
        cagr_pct=cagr if cagr is not None else ret / 3,
        max_drawdown_pct=5.0,
        sharpe_ratio=1.2,
        total_trades=20,
        win_rate_pct=60.0,
        period_days=1095,
    )
    row = ComparisonRow.from_result(r, timeframe, sizer_label=sizer)
    return r, row


class TestFormatComparisonTable:
    def test_empty(self) -> None:
        out = format_comparison_table([])
        assert "없습니다" in out

    def test_single_row_contains_name(self) -> None:
        _, row = _make_result("buy_and_hold", 50.0)
        table = format_comparison_table([row])
        assert "buy_and_hold" in table
        assert "50.00%" in table

    def test_sorted_by_cagr_descending(self) -> None:
        """CAGR 내림차순 정렬 확인."""
        _, row_low = _make_result("strategy_low", 10.0, cagr=5.0)
        _, row_high = _make_result("strategy_high", 80.0, cagr=20.0)
        table = format_comparison_table([row_low, row_high])
        idx_high = table.index("strategy_high")
        idx_low = table.index("strategy_low")
        assert idx_high < idx_low, "CAGR 높은 전략이 먼저 나와야 한다"

    def test_sorted_fallback_to_return_when_cagr_none(self) -> None:
        """CAGR None이면 total_return_pct 폴백으로 정렬."""
        r_low = BacktestResult(
            strategy_name="low", initial_cash=1e7, final_value=1.1e7,
            total_return_pct=10.0, cagr_pct=None, max_drawdown_pct=None,
            sharpe_ratio=None, total_trades=0, win_rate_pct=None, period_days=None,
        )
        r_high = BacktestResult(
            strategy_name="high", initial_cash=1e7, final_value=1.8e7,
            total_return_pct=80.0, cagr_pct=None, max_drawdown_pct=None,
            sharpe_ratio=None, total_trades=0, win_rate_pct=None, period_days=None,
        )
        rows = [ComparisonRow.from_result(r_low, "1d"), ComparisonRow.from_result(r_high, "1d")]
        table = format_comparison_table(rows)
        assert table.index("high") < table.index("low")

    def test_none_displayed_as_na(self) -> None:
        r = BacktestResult(
            strategy_name="no_trades",
            initial_cash=1_000_000.0,
            final_value=1_000_000.0,
            total_return_pct=0.0,
            cagr_pct=None,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            total_trades=0,
            win_rate_pct=None,
            period_days=None,
        )
        row = ComparisonRow.from_result(r, "1d")
        table = format_comparison_table([row])
        assert "N/A" in table

    def test_header_present(self) -> None:
        _, row = _make_result("simple", 20.0)
        table = format_comparison_table([row])
        assert "전략명" in table
        assert "수익률%" in table
        assert "Sharpe" in table
        assert "Sizer" in table

    def test_sizer_label_in_table(self) -> None:
        _, row = _make_result("ema", 30.0, sizer="EmaDynamicSizer")
        table = format_comparison_table([row])
        assert "EmaDynamicSizer" in table

    def test_footnote_present(self) -> None:
        _, row = _make_result("simple", 20.0)
        table = format_comparison_table([row])
        assert "CAGR 내림차순" in table

    def test_timeframe_column(self) -> None:
        _, row = _make_result("timed_hold", 15.0, timeframe="1h")
        table = format_comparison_table([row])
        assert "1h" in table


# ---------------------------------------------------------------------------
# results_to_csv_str
# ---------------------------------------------------------------------------

class TestResultsToCsvStr:
    def test_csv_has_header_and_data(self) -> None:
        r, _ = _make_result("volatility_breakout", 30.0)
        csv_str = results_to_csv_str([r], {"volatility_breakout": "1d"})
        lines = csv_str.strip().splitlines()
        assert len(lines) == 2
        assert "strategy_name" in lines[0]
        assert "volatility_breakout" in lines[1]
        assert "1d" in lines[1]

    def test_csv_multiple_rows(self) -> None:
        r1, _ = _make_result("buy_and_hold", 50.0)
        r2, _ = _make_result("simple", 20.0)
        csv_str = results_to_csv_str([r1, r2], {"buy_and_hold": "1d", "simple": "1d"})
        lines = csv_str.strip().splitlines()
        assert len(lines) == 3  # header + 2 data rows


# ---------------------------------------------------------------------------
# is_bust / 비정상 판정
# ---------------------------------------------------------------------------

def _make_bust_result(name: str, final_value: float, total_return_pct: float) -> BacktestResult:
    return BacktestResult(
        strategy_name=name,
        initial_cash=10_000_000.0,
        final_value=final_value,
        total_return_pct=total_return_pct,
        cagr_pct=None,
        max_drawdown_pct=None,
        sharpe_ratio=None,
        total_trades=0,
        win_rate_pct=None,
        period_days=None,
    )


class TestIsBust:
    def test_zero_final_value_is_bust(self) -> None:
        assert is_bust(final_value=0.0, total_return_pct=-100.0) is True

    def test_negative_final_value_is_bust(self) -> None:
        assert is_bust(final_value=-1.0, total_return_pct=-110.0) is True

    def test_extreme_positive_return_is_bust(self) -> None:
        # 100만% 초과 → 비정상
        assert is_bust(final_value=1e14, total_return_pct=1_000_001.0) is True

    def test_extreme_negative_return_is_bust(self) -> None:
        assert is_bust(final_value=1.0, total_return_pct=-1_000_001.0) is True

    def test_normal_result_not_bust(self) -> None:
        assert is_bust(final_value=12_000_000.0, total_return_pct=20.0) is False

    def test_boundary_exactly_threshold_not_bust(self) -> None:
        # 정확히 임계값(1e6)이면 정상 (> 임계값만 bust)
        assert is_bust(final_value=1e14, total_return_pct=1_000_000.0) is False


class TestBustInComparisonTable:
    def test_bust_result_shows_label_not_number(self) -> None:
        """final_value=0인 결과 → 표에 '청산/비정상' 라벨 표시."""
        r = _make_bust_result("SimpleStrategy", final_value=0.0, total_return_pct=-100.0)
        row = ComparisonRow.from_result(r, "1d")
        assert row.bust is True
        table = format_comparison_table([row])
        assert "청산/비정상" in table
        # 수치가 -100.00% 로 노출되면 안 됨
        assert "-100.00%" not in table

    def test_bust_result_sorted_last(self) -> None:
        """비정상 전략은 정상 전략보다 뒤에 위치해야 한다."""
        r_normal = BacktestResult(
            strategy_name="normal", initial_cash=1e7, final_value=1.2e7,
            total_return_pct=20.0, cagr_pct=6.0, max_drawdown_pct=5.0,
            sharpe_ratio=1.0, total_trades=10, win_rate_pct=60.0, period_days=1095,
        )
        r_bust = _make_bust_result("bust_strategy", final_value=0.0, total_return_pct=-100.0)
        rows = [ComparisonRow.from_result(r_bust, "1d"), ComparisonRow.from_result(r_normal, "1d")]
        table = format_comparison_table(rows)
        assert table.index("normal") < table.index("bust_strategy"), "정상 전략이 비정상 전략보다 먼저 나와야 한다"

    def test_bust_warning_line_present(self) -> None:
        """비정상 전략이 있으면 경고 줄이 포함돼야 한다."""
        r = _make_bust_result("gone", final_value=-5.0, total_return_pct=-150.0)
        table = format_comparison_table([ComparisonRow.from_result(r, "1d")])
        assert "비정상 종료" in table

    def test_extreme_return_column_width_bounded(self) -> None:
        """수익률이 수치 폭발해도 셀 너비가 적정 범위 이내여야 한다."""
        r = _make_bust_result("exploded", final_value=1.0, total_return_pct=2.29e120)
        row = ComparisonRow.from_result(r, "1d")
        table = format_comparison_table([row])
        # 각 줄의 길이가 200자 이내여야 컬럼이 폭발하지 않은 것
        for line in table.splitlines():
            assert len(line) <= 200, f"줄 길이 초과({len(line)}): {line!r}"
