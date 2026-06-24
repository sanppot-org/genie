"""전략 레지스트리

범용 CLI가 전략을 이름으로 선택하여 올바른 파라미터·타임프레임·sizer로
실행할 수 있도록 메타데이터를 한 곳에 모읍니다.

**초기 자본(initial_cash)과 수수료(commission)** 는 전략별 속성이 아닙니다.
이들은 CLI/호출자가 전 전략에 동일하게 적용하는 **전역 설정**입니다 (공정 비교 전제).
StrategySpec은 전략 고유 메타데이터(파라미터·타임프레임·sizer·체결방식)만 담습니다.

Usage:
    from src.backtest.registry import get_strategy, list_strategies

    spec = get_strategy("volatility_breakout")
    print(spec.timeframe)          # "1d"
    print(spec.default_params)     # {"k_value": 0.5}
    print(spec.requires_cheat_on_open)  # False

    names = list_strategies()      # ["buy_and_hold", "ema_alignment", ...]
"""

import dataclasses
from dataclasses import dataclass, field

import backtrader as bt

from src.backtest.sizer_config import SizerConfig
from src.backtest.strategy.buy_and_hold_strategy import BuyAndHoldStrategy
from src.backtest.strategy.ema_alignment_strategy import EmaAlignmentStrategy
from src.backtest.strategy.ema_dynamic_sizer import EmaDynamicSizer
from src.backtest.strategy.ema_simple_alignment_strategy import EmaSimpleAlignmentStrategy
from src.backtest.strategy.morning_afternoon_strategy import MorningAfternoonStrategy
from src.backtest.strategy.simple_strategy import SimpleStrategy
from src.backtest.strategy.split_strategy import SplitStrategy
from src.backtest.strategy.timed_hold_strategy import TimedHoldStrategy
from src.backtest.strategy.volatility_breakout_strategy import VolatilityBreakoutStrategy


@dataclass(frozen=True)
class StrategySpec:
    """단일 전략의 메타데이터.

    initial_cash·commission은 전략별 속성이 아니라 CLI/호출자가 전 전략에
    동일하게 적용하는 전역 설정이므로 이 dataclass에 포함하지 않습니다.

    Attributes:
        name: CLI에서 사용할 짧은 키 (예: "volatility_breakout")
        strategy_class: backtrader Strategy 클래스
        default_params: 전략 params 기본값 (비어있으면 전략 자체 기본값 사용).
            tuple 파라미터(예: ema_periods)는 CLI에서 ast.literal_eval 등으로 파싱 필요.
        timeframe: 캔들 타임프레임 — candle_loader가 반환하는 값과 일치 ("1d"|"1h"|"1m")
        default_sizer: CLI 기본 sizer 대신 사용할 SizerConfig.
            None = CLI 기본 sizer 적용. manages_own_sizing=True이면 sizer 주입 금지.
        manages_own_sizing: True이면 전략이 self.buy(size=...) 등으로 수량을 직접 계산하므로
            외부 sizer를 주입하면 안 됩니다. default_sizer는 None으로 두어야 합니다.
        requires_cheat_on_open: True이면 BacktestBuilder.with_cheat_on_open() 필요
        description: 한 줄 설명
    """

    name: str
    strategy_class: type[bt.Strategy]
    default_params: dict[str, object] = field(default_factory=dict)
    timeframe: str = "1d"
    default_sizer: SizerConfig | None = None
    manages_own_sizing: bool = False
    requires_cheat_on_open: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# 레지스트리 — 8개 전략 등록
# ---------------------------------------------------------------------------

STRATEGY_REGISTRY: dict[str, StrategySpec] = {
    "simple": StrategySpec(
        name="simple",
        strategy_class=SimpleStrategy,
        default_params={"ma_period": 15},
        timeframe="1d",
        default_sizer=SizerConfig.percent(95),
        requires_cheat_on_open=False,
        description="단순 이동평균(SMA) 기반 추세 추종 전략",
    ),
    "volatility_breakout": StrategySpec(
        name="volatility_breakout",
        strategy_class=VolatilityBreakoutStrategy,
        default_params={"k_value": 0.5},
        timeframe="1d",
        default_sizer=SizerConfig.percent(95),
        requires_cheat_on_open=False,
        description="Larry Williams 변동성 돌파 전략 (전일 Range × K)",
    ),
    "ema_alignment": StrategySpec(
        name="ema_alignment",
        strategy_class=EmaAlignmentStrategy,
        default_params={
            "ema_short": 5,
            "ema_mid": 20,
            "ema_long": 40,
            "slope_period": 5,
            "min_gap": 2.0,
            "min_slope": 1.0,
        },
        timeframe="1d",
        # EmaDynamicSizer는 strategy.ema_mid / strategy.ema_long 속성에 직접 접근하므로
        # EmaAlignmentStrategy와 반드시 함께 사용해야 합니다.
        default_sizer=SizerConfig.custom(EmaDynamicSizer),
        requires_cheat_on_open=False,
        description="EMA(5/20/40) 정배열 + 간격/기울기 조건 진입, 정배열 붕괴 청산",
    ),
    "ema_simple_alignment": StrategySpec(
        name="ema_simple_alignment",
        strategy_class=EmaSimpleAlignmentStrategy,
        default_params={
            "ema_periods": (5, 20, 40),
            "enable_long": True,
            "enable_short": True,
            "enable_gap_filter": False,
            "min_gap": 2.0,
        },
        timeframe="1d",
        # EmaSimpleAlignmentStrategy는 self.emas 리스트를 사용하며
        # ema_mid/ema_long 속성이 없으므로 EmaDynamicSizer와 조합하지 않습니다.
        # 숏 포함 전략: PercentSizer는 숏에서 비중 의미가 달라짐(포지션 크기 기준).
        default_sizer=SizerConfig.percent(95),
        requires_cheat_on_open=False,
        description="EMA 정배열/역배열 양방향 전략 (롱·숏 독립 제어)",
    ),
    "split": StrategySpec(
        name="split",
        strategy_class=SplitStrategy,
        default_params={
            "split_count": 10,
            "take_profit_rate": 0.03,
            "trigger_rate": 0.05,
        },
        timeframe="1d",
        # SplitStrategy는 내부에서 initial_cash 기준 고정 금액으로 수량을 계산하므로
        # 외부 sizer 없이 동작합니다.
        default_sizer=None,
        manages_own_sizing=True,
        requires_cheat_on_open=False,
        description="자금 N분할 매수, 각 분할 +3% 익절 / -5% 추가 진입",
    ),
    "timed_hold": StrategySpec(
        name="timed_hold",
        strategy_class=TimedHoldStrategy,
        default_params={"entry_hour": 0, "exit_hour": 12},
        timeframe="1h",
        default_sizer=SizerConfig.percent(95),
        # next_open()을 통해 시가 체결을 사용합니다.
        requires_cheat_on_open=True,
        description="지정 시간에 매수, 지정 시간에 청산하는 시간 기반 홀드 전략 (시가 체결)",
    ),
    "morning_afternoon": StrategySpec(
        name="morning_afternoon",
        strategy_class=MorningAfternoonStrategy,
        default_params={},
        timeframe="1h",
        default_sizer=SizerConfig.percent(95),
        requires_cheat_on_open=False,
        description="전일 오후 수익률·거래량 조건 충족 시 오전 매수, 11시 종가 청산",
    ),
    "buy_and_hold": StrategySpec(
        name="buy_and_hold",
        strategy_class=BuyAndHoldStrategy,
        default_params={},
        timeframe="1d",
        # AllInSizer(retint=False 기본)는 정수 단위 계산이라 고가 자산(코인 등)에서 size=0 가능.
        # PercentSizer(percents=99, retint=False 기본)는 float size를 반환하므로
        # 주식·코인 모두 안전하게 전량 매수에 근접합니다.
        default_sizer=SizerConfig.percent(99),
        requires_cheat_on_open=False,
        description="첫 bar 전량 매수 후 보유 유지 (벤치마크용)",
    ),
}


def get_strategy(name: str) -> StrategySpec:
    """이름으로 전략 스펙을 조회합니다.

    반환되는 StrategySpec의 default_params는 얕은 복사본이므로
    호출자가 dict를 수정해도 레지스트리 원본에 영향을 주지 않습니다.

    Args:
        name: 전략 키 (예: "volatility_breakout")

    Returns:
        StrategySpec 인스턴스 (default_params는 복사본)

    Raises:
        ValueError: 등록되지 않은 이름인 경우 사용 가능한 목록 포함
    """
    spec = STRATEGY_REGISTRY.get(name)
    if spec is None:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        raise ValueError(f"알 수 없는 전략: '{name}'. 사용 가능한 전략: {available}")
    # frozen dataclass이므로 dataclasses.replace()로 복사본 생성
    return dataclasses.replace(spec, default_params=dict(spec.default_params))


def list_strategies() -> list[str]:
    """등록된 전략 이름 목록을 정렬하여 반환합니다.

    Returns:
        전략 이름 문자열 목록 (알파벳 순)
    """
    return sorted(STRATEGY_REGISTRY)
