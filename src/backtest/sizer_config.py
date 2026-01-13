from typing import Any

import backtrader as bt


class SizerConfig:
    """Backtrader Sizer 설정 (클래스 + 파라미터)

    Usage:
        .with_sizer(SizerConfig.percent(95))
        .with_sizer(SizerConfig.all_in())
        .with_sizer(SizerConfig.fixed(100, tranches=5))
        .with_sizer(SizerConfig.custom(MyCustomSizer, param=10))

    Built-in Sizers:
        - PercentSizer: 포트폴리오 비율 기반
        - AllInSizer: 전체 현금 투입
        - FixedSize: 고정 수량
        - PercentSizerInt: 포트폴리오 비율 정수형
        - AllInSizerInt: 전체 현금 정수형
        - FixedReverser: 포지션 반전
        - FixedSizeTarget: 목표 수량
    """

    def __init__(self, sizer_class: type[bt.Sizer], **params: Any) -> None:
        """Sizer 설정 생성

        Args:
            sizer_class: Backtrader Sizer 클래스
            **params: Sizer에 전달할 파라미터
        """
        self.sizer_class = sizer_class
        self.params = params

    @classmethod
    def percent(cls, percents: float) -> "SizerConfig":
        """포트폴리오 비율 기반 Sizer (가장 많이 사용)

        Args:
            percents: 포트폴리오 대비 비율 (예: 10 = 10%)

        Example:
            SizerConfig.percent(95)  # 포트폴리오의 95% 사용
        """
        return cls(bt.sizers.PercentSizer, percents=percents)

    @classmethod
    def all_in(cls) -> "SizerConfig":
        """전체 현금 투입 Sizer (정수 단위)

        Note:
            정수 단위로만 거래됩니다. 암호화폐처럼 소수점 거래가
            필요한 경우 fractional_all_in()을 사용하세요.

        Example:
            SizerConfig.all_in()
        """
        return cls(bt.sizers.AllInSizer)

    @classmethod
    def fixed(cls, stake: int, tranches: int = 1) -> "SizerConfig":
        """고정 수량 Sizer

        Args:
            stake: 고정 수량
            tranches: 분할 횟수 (기본값: 1)

        Example:
            SizerConfig.fixed(100)
            SizerConfig.fixed(100, tranches=5)
        """
        return cls(bt.sizers.FixedSize, stake=stake, tranches=tranches)

    @classmethod
    def custom(cls, sizer_class: type[bt.Sizer], **params: Any) -> "SizerConfig":
        """커스텀 Sizer

        Args:
            sizer_class: 커스텀 Sizer 클래스
            **params: Sizer 파라미터

        Example:
            SizerConfig.custom(DynamicPercentSizer, base_percent=10, max_percent=30)
        """
        return cls(sizer_class, **params)
