from typing import Any

import backtrader as bt
from backtrader import Analyzer, Strategy

from src.backtest.commission_config import CommissionConfig
from src.backtest.data_feed.base import DataFeedConfig
from src.backtest.sizer_config import SizerConfig


class BacktestBuilder:
    """Backtest 설정을 위한 빌더 패턴 클래스"""

    def __init__(self) -> None:
        """빌더 초기화 (기본값 설정)"""
        self.cerebro = bt.Cerebro()
        self._commission_config: CommissionConfig | None = None
        self._initial_cash: float | None = None  # 필수값으로 변경
        self._sizer_config: SizerConfig | None = None
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

    def with_commission(self, commission_config: CommissionConfig) -> "BacktestBuilder":
        """수수료 설정

        Args:
            commission_config: CommissionConfig 인스턴스

        Example:
            .with_commission(CommissionConfig.stock(0.0005))
            .with_commission(CommissionConfig.futures(0.002, margin=2000))
        """
        self._commission_config = commission_config
        return self

    def with_sizer(self, sizer_config: SizerConfig) -> "BacktestBuilder":
        """Sizer 설정

        Args:
            sizer_config: SizerConfig 인스턴스

        Example:
            .with_sizer(SizerConfig.percent(95))
            .with_sizer(SizerConfig.all_in())
            .with_sizer(SizerConfig.custom(DynamicPercentSizer, base_percent=10))
        """
        self._sizer_config = sizer_config
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

    def add_data(self, data_config: DataFeedConfig) -> "BacktestBuilder":
        """데이터 피드 설정 추가

        Args:
            data_config: DataFeedConfig 인스턴스

        Returns:
            BacktestBuilder: 체이닝을 위한 self 반환

        Example:
            >>> from src.backtest.data_feed.pandas import PandasDataFeedConfig
            >>> import pandas as pd
            >>>
            >>> df = pd.DataFrame({
            ...     'open': [100, 101],
            ...     'high': [105, 106],
            ...     'low': [99, 100],
            ...     'close': [103, 104],
            ...     'volume': [1000, 2000]
            ... }, index=pd.DatetimeIndex(['2024-01-01', '2024-01-02']))
            >>> config = PandasDataFeedConfig.create(df, name='BTC-KRW')
            >>> builder.add_data(config)
        """
        data_feed = data_config.to_data_feed()
        self._data_feeds.append(data_feed)
        return self

    def _validate_required_fields(self) -> None:
        """필수 필드 검증"""
        if self._initial_cash is None:
            raise ValueError("초기 자본이 설정되지 않았습니다. with_initial_cash()를 호출해주세요.")

        if self._strategy_class is None:
            raise ValueError("전략이 설정되지 않았습니다. with_strategy()를 호출해주세요.")

        if not self._data_feeds:
            raise ValueError("데이터 피드가 추가되지 않았습니다. add_data()를 호출해주세요.")

    def build(self) -> bt.Cerebro:
        """Cerebro 인스턴스 구성 (backtrader 권장 순서)"""
        # 필수값 검증
        self._validate_required_fields()

        # 1. 전략 추가
        self.cerebro.addstrategy(self._strategy_class, **self._strategy_params)

        # 2. 데이터 피드 추가
        for data_feed in self._data_feeds:
            self.cerebro.adddata(data_feed)

        # 3. Broker 설정
        self.cerebro.broker.setcash(self._initial_cash)

        # 4. Commission 설정 (설정된 경우만)
        if self._commission_config:
            self.cerebro.broker.setcommission(**self._commission_config.to_kwargs())

        # 5. 슬리피지 설정
        if self._slippage:
            self.cerebro.broker.set_slippage_perc(perc=self._slippage)

        # 6. Position sizer 설정 (설정된 경우만)
        if self._sizer_config:
            self.cerebro.addsizer(self._sizer_config.sizer_class, **self._sizer_config.params)

        # 7. 분석기 추가
        for analyzer_class, name in self._analyzers:
            self.cerebro.addanalyzer(analyzer_class, _name=name)

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
