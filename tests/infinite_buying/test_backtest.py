"""무한매수법 백테스트 하니스 (순수) — 체결 시뮬레이션 + 사이클 검증."""

from datetime import date, timedelta

import pytest

from src.infinite_buying.backtest import BacktestConfig, DailyBar, run_backtest


def _bars(closes: list[float], highs: list[float] | None = None) -> list[DailyBar]:
    """종가 리스트로 일봉 생성 (high 미지정 시 close와 동일)."""
    base = date(2024, 1, 1)
    hs = highs if highs is not None else closes
    return [DailyBar(date=base + timedelta(days=i), high=hs[i], close=closes[i]) for i in range(len(closes))]


def _cfg(allocation: float = 10000.0) -> BacktestConfig:
    return BacktestConfig(division=40, base_gap=15.0, sell_limit_pct=15.0, allocation=allocation)


def test_no_trades_when_price_never_triggers_first_buy() -> None:
    # 첫매수 목표가 = 전일종가×1.15. 종가가 계속 상승하면(>목표가) LOC 매수 미체결 → 보유 0 유지.
    bars = _bars([100.0, 130.0, 170.0])  # day1: prev=100→target=115, close130>115 미체결; day2: prev130→target149.5, close170>149.5 미체결
    result = run_backtest(bars, _cfg())
    assert result.num_buys == 0
    assert result.num_cycles == 0
    assert result.final_equity == pytest.approx(10000.0)  # 현금 전액 보존
    assert result.total_return == pytest.approx(0.0)


def test_first_buy_fills_when_close_below_target() -> None:
    # day1: prev=100 → target=115, close=50<=115 → 첫매수 체결. 회당금액=allocation/division=250, qty=floor(250/50)=5.
    bars = _bars([100.0, 50.0])
    result = run_backtest(bars, _cfg())
    assert result.num_buys == 1
    # 보유 5주 @50 → equity = (10000-250) + 5*50 = 9750+250 = 10000 (체결 직후 동일가)
    assert result.final_equity == pytest.approx(10000.0)
    assert result.num_cycles == 0  # 아직 청산 전


def test_full_cycle_buy_then_profitable_limit_sell() -> None:
    # day1 첫매수(close=50, qty5), day2 지정가매도(평단50×1.15=57.5, high=60>=57.5 체결).
    # 첫매수 후 보유5 평단50. day2 plan: 전반전 → 별지점매수/평단매수 + 쿼터매도/지정가매도.
    # day2 close=60 (>별지점, >평단 → 매수 미체결), high=60 → limit_sell(57.5) 체결, quarter_sell(별지점)도 close>=별지점이면 체결.
    bars = _bars([100.0, 50.0, 60.0], highs=[100.0, 50.0, 60.0])
    result = run_backtest(bars, _cfg())
    assert result.num_buys >= 1
    assert result.num_sells >= 1
    # 수익 실현으로 최종 자산 > 초기 (매도가 일부라도 이익)
    assert result.final_equity > 10000.0
    assert result.num_days == 3


def test_metrics_have_expected_shape() -> None:
    bars = _bars([100.0, 50.0, 45.0, 70.0], highs=[100.0, 55.0, 48.0, 75.0])
    result = run_backtest(bars, _cfg())
    assert result.num_days == 4
    assert 0.0 <= result.max_drawdown <= 1.0
    assert result.num_buys >= 0 and result.num_sells >= 0


def test_empty_or_single_bar_returns_flat() -> None:
    assert run_backtest([], _cfg()).total_return == pytest.approx(0.0)
    one = run_backtest(_bars([100.0]), _cfg())
    assert one.num_days == 1 and one.num_buys == 0 and one.final_equity == pytest.approx(10000.0)
