from typing import Any


class CommissionConfig:
    """Backtrader Commission 설정 (수수료 + 파라미터)

    Usage:
        .with_commission(CommissionConfig.stock(0.0005))
        .with_commission(CommissionConfig.futures(0.002, margin=2000))
        .with_commission(CommissionConfig.custom(0.001, mult=1.5))

    Commission Types:
        - Stock: 주식형 거래 (가장 많이 사용)
        - Futures: 선물형 거래 (마진, 승수 설정)
        - Custom: 커스텀 설정
    """

    def __init__(
        self,
        commission: float,
        margin: float | None = None,
        mult: float = 1.0,
        stocklike: bool = True,
    ) -> None:
        """Commission 설정 생성

        Args:
            commission: 수수료율 (예: 0.001 = 0.1%)
            margin: 마진 (선물/옵션 거래 시)
            mult: 승수
            stocklike: 주식형(True) vs 선물형(False)
        """
        self.commission = commission
        self.margin = margin
        self.mult = mult
        self.stocklike = stocklike

    @classmethod
    def stock(cls, commission: float) -> "CommissionConfig":
        """주식형 수수료 (가장 많이 사용)

        Args:
            commission: 수수료율 (예: 0.0005 = 0.05%)

        Example:
            CommissionConfig.stock(0.0005)  # Upbit 0.05%
            CommissionConfig.stock(0.002)   # 일반 주식 0.2%
        """
        return cls(commission=commission, stocklike=True)

    @classmethod
    def futures(
        cls, commission: float, margin: float, mult: float = 1.0
    ) -> "CommissionConfig":
        """선물형 수수료

        Args:
            commission: 수수료율
            margin: 마진 (증거금)
            mult: 승수 (기본값: 1.0)

        Example:
            CommissionConfig.futures(0.002, margin=2000, mult=10)
        """
        return cls(commission=commission, margin=margin, mult=mult, stocklike=False)

    @classmethod
    def custom(
        cls,
        commission: float,
        margin: float | None = None,
        mult: float = 1.0,
        stocklike: bool = True,
    ) -> "CommissionConfig":
        """커스텀 수수료 설정

        Args:
            commission: 수수료율
            margin: 마진 (선택)
            mult: 승수 (기본값: 1.0)
            stocklike: 주식형(True) vs 선물형(False)

        Example:
            CommissionConfig.custom(0.001, mult=1.5)
            CommissionConfig.custom(0.002, margin=1000, mult=5, stocklike=False)
        """
        return cls(commission=commission, margin=margin, mult=mult, stocklike=stocklike)

    def to_kwargs(self) -> dict[str, Any]:
        """backtrader setcommission()에 전달할 kwargs 생성

        Returns:
            commission, mult, stocklike를 포함한 dict
            margin이 있으면 포함
        """
        kwargs: dict[str, Any] = {
            "commission": self.commission,
            "mult": self.mult,
            "stocklike": self.stocklike,
        }
        if self.margin is not None:
            kwargs["margin"] = self.margin
        return kwargs
