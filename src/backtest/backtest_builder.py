from datetime import date
from typing import Any

import backtrader as bt
from backtrader import Analyzer, Strategy, TimeFrame

from src.backtest.commission_config import CommissionConfig
from src.backtest.data_feed.base import DataFeedConfig
from src.backtest.result import BacktestResult, _compute_cagr, _compute_total_return_pct, _safe_max_drawdown, _safe_sharpe, _safe_trade_stats, build_equity_curve
from src.backtest.sizer_config import SizerConfig

# 표준 분석기 번들: (analyzer_class, name, params_dict)
# SharpeRatio는 timeframe=Days + annualize=True 로 연율화된 샤프를 반환하도록 설정
# TimeReturn은 timeframe=Days 로 일별 수익률 시계열을 수집 (1h/1m 전략도 일 단위로 집계됨)
_STANDARD_ANALYZERS: list[tuple[type[Analyzer], str, dict[str, object]]] = [
    (bt.analyzers.Returns, "returns", {}),
    (bt.analyzers.SharpeRatio, "sharpe", {"timeframe": TimeFrame.Days, "annualize": True}),
    (bt.analyzers.DrawDown, "drawdown", {}),
    (bt.analyzers.TradeAnalyzer, "trades", {}),
    (bt.analyzers.TimeReturn, "timereturn", {"timeframe": TimeFrame.Days}),
]

# with_analyzer()에서 사용 불가한 예약 이름 집합
_RESERVED_ANALYZER_NAMES: frozenset[str] = frozenset({"returns", "sharpe", "drawdown", "trades", "timereturn"})


class BacktestBuilder:
    """Backtest 설정을 위한 빌더 패턴 클래스"""

    def __init__(self) -> None:
        """빌더 초기화 (기본값 설정)"""
        self.cerebro: bt.Cerebro | None = None
        self._commission_config: CommissionConfig | None = None
        self._initial_cash: float | None = None  # 필수값으로 변경
        self._sizer_config: SizerConfig | None = None
        self._strategy_class: type[Strategy] | None = None
        self._strategy_params: dict[str, object] = {}
        self._slippage: float | None = None
        self._cheat_on_open: bool = False  # 시가 체결 옵션
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

    def with_cheat_on_open(self, enabled: bool = True) -> "BacktestBuilder":
        """시가 체결 옵션 설정

        True로 설정하면 주문이 현재 bar의 시가로 체결됩니다.
        기본값(False)은 다음 bar의 시가로 체결됩니다.

        Args:
            enabled: True면 현재 bar 시가 체결, False면 다음 bar 시가 체결
        """
        self._cheat_on_open = enabled
        return self

    def with_analyzer(self, analyzer_class: type[Analyzer], name: str) -> "BacktestBuilder":
        """분석기 추가.

        Args:
            analyzer_class: backtrader Analyzer 서브클래스.
            name: 분석기 식별 이름. 표준 번들 예약어({'returns','sharpe','drawdown','trades'})는 사용 불가.

        Raises:
            ValueError: name이 표준 분석기 예약어인 경우.
        """
        if name in _RESERVED_ANALYZER_NAMES:
            raise ValueError(f"'{name}'는 표준 분석기 예약어입니다. 다른 이름을 사용해주세요.")
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

        # Cerebro 생성 (cheat_on_open 옵션 적용)
        self.cerebro = bt.Cerebro(cheat_on_open=self._cheat_on_open)

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

        # 5. 슬리피지 설정 (0.0도 유효한 값이므로 None 비교)
        if self._slippage is not None:
            self.cerebro.broker.set_slippage_perc(perc=self._slippage)

        # 6. Position sizer 설정 (설정된 경우만)
        if self._sizer_config:
            self.cerebro.addsizer(self._sizer_config.sizer_class, **self._sizer_config.params)

        # 7. 표준 분석기 번들 기본 부착 (params 포함)
        user_names = {name for _, name in self._analyzers}
        for analyzer_class, name, params in _STANDARD_ANALYZERS:
            if name not in user_names:
                self.cerebro.addanalyzer(analyzer_class, _name=name, **params)

        # 8. 사용자 지정 분석기 추가
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

    def run_with_result(self, strategy_name: str | None = None) -> BacktestResult:
        """백테스트 실행 후 표준화된 BacktestResult 반환.

        CAGR은 첫 봉~마지막 봉 사이의 실제 캘린더 일수를 기반으로 계산합니다.
        타임프레임(1d/1h/1m)이나 자산 종류(주식/코인)에 무관하게 정확합니다.

        Args:
            strategy_name: 결과에 기록할 전략 이름. None이면 전략 클래스명 사용.

        Returns:
            BacktestResult: 표준 지표를 담은 frozen dataclass.
        """
        results = self.run()
        strat = results[0]

        name = strategy_name or (self._strategy_class.__name__ if self._strategy_class else "Unknown")
        initial_cash = float(self._initial_cash or 0.0)
        final_value = float(self.cerebro.broker.getvalue()) if self.cerebro else 0.0

        total_return_pct = _compute_total_return_pct(initial_cash, final_value)

        # DrawDown 분석기
        drawdown_analysis = strat.analyzers.drawdown.get_analysis()
        max_drawdown_pct = _safe_max_drawdown(drawdown_analysis)

        # SharpeRatio 분석기 (timeframe=Days, annualize=True로 연율화)
        sharpe_analysis = strat.analyzers.sharpe.get_analysis()
        sharpe_ratio = _safe_sharpe(sharpe_analysis)

        # TradeAnalyzer 분석기
        trade_analysis = strat.analyzers.trades.get_analysis()
        total_trades, win_rate_pct = _safe_trade_stats(trade_analysis)

        # TimeReturn 분석기 → 일별 자산곡선 (equity curve + drawdown)
        equity_curve = build_equity_curve(strat.analyzers.timereturn.get_analysis())

        # period_days: 첫 봉~마지막 봉 사이의 실제 캘린더 일수.
        # data.datetime.datetime(ago) 는 linebuffer.LineBuffer.datetime()을 호출하며,
        # array[idx + ago] → num2date() 순으로 동작한다.
        # ago=0: 마지막(현재) 봉, ago=-(n_bars-1): 첫 봉.
        period_days: int | None = None
        start_date: date | None = None
        end_date: date | None = None
        try:
            data = strat.datas[0]
            n_bars = len(data)
            if n_bars >= 1:
                last_dt = data.datetime.datetime(0)
                first_dt = data.datetime.datetime(-(n_bars - 1))
                start_date = first_dt.date()
                end_date = last_dt.date()
                if n_bars >= 2:  # 단일 봉은 기간 산출 불가(period_days=None)
                    period_days = (last_dt - first_dt).days
                    if period_days <= 0:
                        period_days = None
        except (AttributeError, IndexError, TypeError):
            pass

        # CAGR: 실제 캘린더 기간(period_days) 기반. 타임프레임/자산 종류 무관.
        cagr_pct: float | None = _compute_cagr(initial_cash, final_value, period_days)

        return BacktestResult(
            strategy_name=name,
            initial_cash=initial_cash,
            final_value=final_value,
            total_return_pct=total_return_pct,
            cagr_pct=cagr_pct,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            win_rate_pct=win_rate_pct,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
            equity_curve=equity_curve,
        )

    def run_and_plot(self) -> list[Any]:  # type: ignore[misc]
        """백테스트 실행 및 차트 출력"""
        results = self.run()
        if self.cerebro is not None:
            self.cerebro.plot()
        return results
