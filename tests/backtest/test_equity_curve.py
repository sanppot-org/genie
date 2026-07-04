"""equity curve(자산곡선) 산출 검증 — build_equity_curve + _build_benchmark."""

from collections import OrderedDict
from datetime import date, datetime

import pandas as pd
import pytest

from src.backtest.result import build_equity_curve
from src.service.backtest_service import _build_benchmark


class TestBuildEquityCurve:
    def test_누적수익률과_낙폭을_계산한다(self):
        # 일별 수익률: +10% → -20% → +25% (누적: 1.1 → 0.88 → 1.10)
        analysis = OrderedDict([
            (datetime(2024, 1, 2), 0.10),
            (datetime(2024, 1, 3), -0.20),
            (datetime(2024, 1, 4), 0.25),
        ])

        curve = build_equity_curve(analysis)

        assert curve is not None and len(curve) == 3
        assert curve[0].date == date(2024, 1, 2)
        assert curve[0].return_pct == pytest.approx(10.0)
        assert curve[0].drawdown_pct == pytest.approx(0.0)
        # 고점 1.1 대비 0.88 → -20%
        assert curve[1].return_pct == pytest.approx(-12.0)
        assert curve[1].drawdown_pct == pytest.approx(-20.0)
        # 0.88 * 1.25 = 1.1 → 고점 회복 (drawdown 0)
        assert curve[2].return_pct == pytest.approx(10.0)
        assert curve[2].drawdown_pct == pytest.approx(0.0)

    def test_빈_분석결과나_비정상_입력이면_None(self):
        assert build_equity_curve(OrderedDict()) is None
        assert build_equity_curve(None) is None


class TestBuildBenchmark:
    def test_종가_기반_수익률과_낙폭을_계산한다(self):
        df = pd.DataFrame(
            {"close": [100.0, 110.0, 88.0, 110.0]},
            index=pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
        )

        curve = _build_benchmark(df)

        assert curve is not None and len(curve) == 4
        assert curve[0].return_pct == pytest.approx(0.0)
        assert curve[2].return_pct == pytest.approx(-12.0)
        assert curve[2].drawdown_pct == pytest.approx(-20.0)  # 고점 110 대비 88
        assert curve[3].drawdown_pct == pytest.approx(0.0)

    def test_분봉은_일별_마지막_종가로_집계한다(self):
        df = pd.DataFrame(
            {"close": [100.0, 105.0, 105.0, 120.0]},
            index=pd.DatetimeIndex([
                "2024-01-02 10:00", "2024-01-02 15:30",
                "2024-01-03 10:00", "2024-01-03 15:30",
            ]),
        )

        curve = _build_benchmark(df)

        assert curve is not None and len(curve) == 2
        assert curve[0].date == date(2024, 1, 2)
        assert curve[0].return_pct == pytest.approx(0.0)  # 첫날 마지막 종가 105 기준
        assert curve[1].return_pct == pytest.approx((120.0 / 105.0 - 1) * 100)

    def test_빈_데이터면_None(self):
        assert _build_benchmark(None) is None
        assert _build_benchmark(pd.DataFrame()) is None
