"""EMA 기울기/간격 기반 동적 포지션 사이저"""

from typing import Any

import backtrader as bt


class EmaDynamicSizer(bt.Sizer):
    """EMA 기울기/간격 기반 동적 포지션 사이저

    EMA 20일선과 40일선의 기울기와 간격을 기반으로
    매수 비중을 동적으로 결정합니다.

    - 기울기가 가파를수록 → 추세가 강함 → 비중 증가
    - 간격이 넓을수록 → 추세가 강함 → 비중 증가

    Params:
        slope_period: 기울기 계산 기간 (기본: 5일)
        max_slope: 최대 기울기 기준 (기본: 5%)
        max_gap: 최대 간격 기준 (기본: 10%)
        min_weight: 최소 비중 (기본: 30%)
        max_weight: 최대 비중 (기본: 100%)
        slope_weight: 기울기 점수 가중치 (기본: 0.5)
        gap_weight: 간격 점수 가중치 (기본: 0.5)

    Example:
        >>> cerebro.addsizer(EmaDynamicSizer,
        ...     slope_period=5,
        ...     max_slope=5.0,
        ...     max_gap=10.0,
        ...     min_weight=0.3,
        ...     max_weight=1.0
        ... )
    """

    params = (
        ('slope_period', 5),
        ('max_slope', 5.0),
        ('max_gap', 10.0),
        ('min_weight', 0.3),
        ('max_weight', 1.0),
        ('slope_weight', 0.5),
        ('gap_weight', 0.5),
    )

    def _getsizing(
            self,
            comminfo: Any,
            cash: float,
            data: Any,
            isbuy: bool
    ) -> int:
        """매수/매도 수량 계산

        Args:
            comminfo: 수수료 정보
            cash: 사용 가능 현금
            data: 데이터 피드
            isbuy: 매수 여부

        Returns:
            매수/매도 수량
        """
        # 매도 시: 보유 전량
        if not isbuy:
            position = self.broker.getposition(data)
            return position.size

        # 전략에서 EMA 값 가져오기
        strategy = self.strategy

        # EMA 속성이 없으면 기본 비중 사용
        if not hasattr(strategy, 'ema_mid') or not hasattr(strategy, 'ema_long'):
            weight = self.p.min_weight
            price = data.close[0]
            return int((cash * weight) / price)

        ema20 = strategy.ema_mid[0]
        ema40 = strategy.ema_long[0]

        # 기울기 계산을 위한 이전 값
        slope_period = self.p.slope_period
        try:
            ema20_prev = strategy.ema_mid[-slope_period]
            ema40_prev = strategy.ema_long[-slope_period]
        except IndexError:
            # 데이터 부족 시 기본 비중 사용
            weight = self.p.min_weight
            price = data.close[0]
            return int((cash * weight) / price)

        # 기울기 계산 (%)
        slope_20 = (ema20 - ema20_prev) / ema20_prev * 100 if ema20_prev != 0 else 0
        slope_40 = (ema40 - ema40_prev) / ema40_prev * 100 if ema40_prev != 0 else 0
        avg_slope = (slope_20 + slope_40) / 2

        # 간격 계산 (%)
        gap_ratio = (ema20 - ema40) / ema40 * 100 if ema40 != 0 else 0

        # 점수 계산 (0~1)
        slope_score = min(1.0, max(0, avg_slope / self.p.max_slope))
        gap_score = min(1.0, max(0, gap_ratio / self.p.max_gap))

        # 최종 비중 계산
        combined_score = (
                slope_score * self.p.slope_weight +
                gap_score * self.p.gap_weight
        )
        weight = self.p.min_weight + (self.p.max_weight - self.p.min_weight) * combined_score

        # 수량 계산
        price = data.close[0]
        size = int((cash * weight) / price)

        return size
