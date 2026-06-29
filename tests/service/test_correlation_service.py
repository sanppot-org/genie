"""Tests for correlation_service.compute_correlation — 핵심 통계 로직."""

from datetime import date

import pandas as pd
import pytest

from src.service.correlation_service import compute_correlation


def _series(start: date, values: list[float]) -> pd.Series:
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def _price_from_returns(base: float, returns: list[float]) -> list[float]:
    """수익률 시퀀스로 가격 시계열 생성(첫 값 = base)."""
    prices = [base]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return prices


class TestComputeCorrelation:
    def test_완전_양의_상관(self) -> None:
        # 동일한 수익률 시퀀스 → 수익률 상관 = +1.0
        rets = [0.1, -0.05, 0.2, -0.1]
        a = _series(date(2024, 1, 1), _price_from_returns(100, rets))
        b = _series(date(2024, 1, 1), _price_from_returns(50, rets))

        out = compute_correlation({"A": a, "B": b})

        assert out.tickers == ["A", "B"]
        assert out.matrix[0][0] == 1.0
        assert out.matrix[0][1] == pytest.approx(1.0)
        assert out.matrix[1][0] == pytest.approx(1.0)
        assert out.observations == len(rets)  # pct_change로 첫 행 제거
        assert out.dropped == []

    def test_완전_음의_상관(self) -> None:
        # 수익률이 정확히 부호 반대 → 수익률 벡터의 피어슨 상관 = -1.0
        rets = [0.1, -0.05, 0.2, -0.1]
        neg = [-r for r in rets]
        a = _series(date(2024, 1, 1), _price_from_returns(100, rets))
        b = _series(date(2024, 1, 1), _price_from_returns(100, neg))

        out = compute_correlation({"A": a, "B": b})

        assert out.matrix[0][1] == pytest.approx(-1.0)

    def test_기간_불일치_공통구간만_사용(self) -> None:
        # A: 1/1~1/5, B: 1/3~1/7 → 공통 1/3,1/4,1/5(가격) → 수익률 2개.
        # 공통구간 수익률이 변동해야(분산>0) 상관 정의됨.
        a = _series(date(2024, 1, 1), [100, 110, 121, 133.1, 120.0])
        b = _series(date(2024, 1, 3), [121, 133.1, 120.0, 130.0, 140.0])

        out = compute_correlation({"A": a, "B": b})

        assert out.observations == 2
        assert out.period_start == date(2024, 1, 4)
        assert out.period_end == date(2024, 1, 5)
        assert out.matrix[0][1] == pytest.approx(1.0)

    def test_빈_시계열은_dropped(self) -> None:
        a = _series(date(2024, 1, 1), _price_from_returns(100, [0.1, -0.05, 0.2]))
        empty = pd.Series([], dtype="float64")

        out = compute_correlation({"A": a, "EMPTY": empty})

        assert "EMPTY" in out.dropped
        assert "A" not in out.dropped
        # 유효 티커 1개 → 계산 불가, 경고 포함
        assert out.observations == 0
        assert out.warnings

    def test_가격상관_옵션(self) -> None:
        # 선형 가격 → price 상관 = ±1.0 (추세 포함)
        a = _series(date(2024, 1, 1), [1, 2, 3, 4, 5])
        b = _series(date(2024, 1, 1), [10, 8, 6, 4, 2])

        out = compute_correlation({"A": a, "B": b}, return_type="price")

        assert out.return_type == "price"
        assert out.observations == 5  # 가격은 pct_change 안 함
        assert out.matrix[0][1] == pytest.approx(-1.0)

    def test_spearman_method(self) -> None:
        rets = [0.1, -0.05, 0.2, -0.1]
        a = _series(date(2024, 1, 1), _price_from_returns(100, rets))
        b = _series(date(2024, 1, 1), _price_from_returns(50, rets))

        out = compute_correlation({"A": a, "B": b}, method="spearman")

        assert out.method == "spearman"
        assert out.matrix[0][1] == pytest.approx(1.0)

    def test_잘못된_method_예외(self) -> None:
        a = _series(date(2024, 1, 1), [1, 2, 3])
        with pytest.raises(ValueError, match="method"):
            compute_correlation({"A": a, "B": a}, method="kendall")

    def test_상수_시계열_상관_None_대각은_1(self) -> None:
        # 분산 0인 시계열(상수) → off-diagonal 상관 불가 → None + 경고.
        # 단 대각(자기상관)은 계약상 항상 1.0이어야 한다.
        flat = _series(date(2024, 1, 1), [100, 100, 100, 100])
        moving = _series(date(2024, 1, 1), _price_from_returns(100, [0.1, -0.05, 0.2]))

        out = compute_correlation({"FLAT": flat, "MOV": moving})

        assert out.matrix[0][1] is None
        assert out.matrix[0][0] == 1.0  # 대각 강제
        assert out.matrix[1][1] == 1.0
        assert out.warnings

    def test_0가격_inf_오염_차단(self) -> None:
        # 거래정지/오류로 0이 섞이면 pct_change가 ±inf 생성. dropna가 inf를 못 거르면
        # 허위 상관이 조용히 산출됨. inf→NaN 치환으로 해당 관측이 제거되어야 한다.
        a = _series(date(2024, 1, 1), [100, 0, 50, 60, 70])
        b = _series(date(2024, 1, 1), [10, 11, 12, 13, 14])

        out = compute_correlation({"A": a, "B": b})

        # 0→50 수익률은 ±inf(0으로 나눔)라 제거됨 → naive 4관측에서 1개 감소.
        # (100→0은 -100%라는 유효 수익률이므로 유지된다.)
        assert out.observations == 3
        # 핵심: 산출된 상관계수에 inf/비정상 값이 새지 않아야 함
        for row in out.matrix:
            for v in row:
                assert v is None or -1.0 <= v <= 1.0

    def test_3티커_대칭성_정방행렬(self) -> None:
        rets_a = [0.1, -0.05, 0.2, -0.1, 0.03]
        rets_b = [0.05, -0.02, 0.1, -0.05, 0.01]
        rets_c = [-r for r in rets_a]
        a = _series(date(2024, 1, 1), _price_from_returns(100, rets_a))
        b = _series(date(2024, 1, 1), _price_from_returns(100, rets_b))
        c = _series(date(2024, 1, 1), _price_from_returns(100, rets_c))

        out = compute_correlation({"A": a, "B": b, "C": c})

        n = len(out.tickers)
        assert n == 3
        assert all(len(row) == n for row in out.matrix)  # 정방
        for i in range(n):
            assert out.matrix[i][i] == 1.0  # 대각
            for j in range(n):
                assert out.matrix[i][j] == pytest.approx(out.matrix[j][i])  # 대칭
        assert out.matrix[0][2] == pytest.approx(-1.0)  # A vs C 완전 음의
