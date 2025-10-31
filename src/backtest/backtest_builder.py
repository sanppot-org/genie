from typing import Any

import backtrader as bt
from backtrader import Analyzer, Strategy


class BacktestBuilder:
    """Backtest 설정을 위한 빌더 패턴 클래스"""

    def __init__(self) -> None:
        """빌더 초기화 (기본값 설정)"""
        self.cerebro = bt.Cerebro()
        self._commission = 0.001
        self._commission_margin: float | None = None
        self._commission_mult = 1.0
        self._commission_stocklike = True
        self._initial_cash: float | None = None  # 필수값으로 변경
        self._position_percents = 10.0  # 포트폴리오의 10%
        self._strategy_class: type[Strategy] | None = None
        self._strategy_params: dict[str, object] = {}
        self._slippage: float | None = None
        self._analyzers: list[tuple[type[Analyzer], str]] = []
        self._data_feeds: list[bt.AbstractDataBase] = []

    def with_initial_cash(self, cash: float) -> "BacktestBuilder":
        """초기 자본 설정 (필수)"""
        if cash <= 0:
            raise ValueError(f"초기 자본은 0보다 커야 합니다: {cash}")
        self._initial_cash = cash
        return self

    def with_commission(
        self,
        commission: float,
        margin: float | None = None,
        mult: float = 1.0,
        stocklike: bool = True,
    ) -> "BacktestBuilder":
        """수수료 설정

        Args:
            commission: 수수료율 (예: 0.001 = 0.1%)
            margin: 마진 (선물/옵션 거래 시)
            mult: 승수
            stocklike: 주식형(True) vs 선물형(False)
        """
        self._commission = commission
        self._commission_margin = margin
        self._commission_mult = mult
        self._commission_stocklike = stocklike
        return self

    def with_position_size(self, percents: float) -> "BacktestBuilder":
        """포지션 크기 설정

        Args:
            percents: 포트폴리오 대비 비율 (예: 10 = 포트폴리오의 10%)
        """
        self._position_percents = percents
        return self

    def with_slippage(self, perc: float) -> "BacktestBuilder":
        """슬리피지 설정"""
        self._slippage = perc
        return self

    def with_analyzer(self, analyzer_class: type[Analyzer], name: str) -> "BacktestBuilder":
        """분석기 추가"""
        self._analyzers.append((analyzer_class, name))
        return self

    def with_strategy(self, strategy_class: type[Strategy], **params: object) -> "BacktestBuilder":
        """전략 및 파라미터 설정"""
        self._strategy_class = strategy_class
        self._strategy_params = params
        return self

    def add_data(self, data_feed: bt.AbstractDataBase) -> "BacktestBuilder":
        """외부에서 준비된 데이터 피드 추가"""
        self._data_feeds.append(data_feed)
        return self

    def build(self) -> bt.Cerebro:
        """Cerebro 인스턴스 구성"""
        # 필수값 검증
        if self._initial_cash is None:
            raise ValueError("초기 자본이 설정되지 않았습니다. with_initial_cash()를 호출해주세요.")

        if self._strategy_class is None:
            raise ValueError("전략이 설정되지 않았습니다. with_strategy()를 호출해주세요.")

        if not self._data_feeds:
            import warnings

            warnings.warn(
                "데이터 피드가 추가되지 않았습니다. add_data()를 호출해주세요.",
                UserWarning,
                stacklevel=2,
            )

        # Broker 설정
        self.cerebro.broker.setcash(self._initial_cash)

        # Commission 설정
        commission_kwargs = {
            "commission": self._commission,
            "mult": self._commission_mult,
            "stocklike": self._commission_stocklike,
        }
        if self._commission_margin is not None:
            commission_kwargs["margin"] = self._commission_margin

        self.cerebro.broker.setcommission(**commission_kwargs)

        # Position sizer 설정
        self.cerebro.addsizer(bt.sizers.PercentSizer, percents=self._position_percents)

        # 슬리피지 설정
        if self._slippage:
            self.cerebro.broker.set_slippage_perc(perc=self._slippage)

        # 분석기 추가
        for analyzer_class, name in self._analyzers:
            self.cerebro.addanalyzer(analyzer_class, _name=name)

        # 전략 추가
        self.cerebro.addstrategy(self._strategy_class, **self._strategy_params)

        # 데이터 피드 추가
        for data_feed in self._data_feeds:
            self.cerebro.adddata(data_feed)

        return self.cerebro

    def run(self) -> list[Any]:  # type: ignore[misc]
        """백테스트 실행 및 결과 반환"""
        cerebro = self.build()

        print(f"\nStarting Portfolio Value: {cerebro.broker.getvalue():.2f}")
        results = cerebro.run()
        print(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f}")

        return results

    def run_and_plot(self) -> list[Any]:  # type: ignore[misc]
        """백테스트 실행 및 차트 출력"""
        results = self.run()
        self.cerebro.plot()
        return results
