"""백테스트 CLI 공유 로직 — 파라미터 파서 + 비교표 포맷터.

scripts/backtest.py가 얇게 호출하는 순수 함수 모음.
DB 의존성 없음 → tests/backtest/test_cli.py에서 DB 없이 검증 가능.
"""

from __future__ import annotations

import ast
import csv
from dataclasses import dataclass, field
import io
import math

from src.backtest.result import BacktestResult
from src.backtest.sizer_config import SizerConfig

# 비정상 판정 임계값
# - final_value <= 0: 파산·청산 (포트폴리오 가치가 0 이하)
# - abs(total_return_pct) > 1e6: 1만 배(100만%) 초과 → 수치 폭발 추정
_BUST_RETURN_THRESHOLD: float = 1_000_000.0  # 100만%


def is_bust(final_value: float, total_return_pct: float) -> bool:
    """비정상 결과 판정.

    다음 중 하나라도 해당하면 True:
    - final_value <= 0 (파산·청산)
    - abs(total_return_pct) > 1e6 (수치 폭발)
    - total_return_pct 가 NaN/inf (부동소수점 오버플로)

    Args:
        final_value: 최종 포트폴리오 가치
        total_return_pct: 총수익률 (%)

    Returns:
        True면 비정상(BUST), False면 정상
    """
    if final_value <= 0:
        return True
    if not math.isfinite(total_return_pct):
        return True
    if abs(total_return_pct) > _BUST_RETURN_THRESHOLD:
        return True
    return False

# ---------------------------------------------------------------------------
# --param 파서
# ---------------------------------------------------------------------------

def parse_param_override(raw: str) -> tuple[str, object]:
    """``key=value`` 형식의 --param 문자열을 (key, typed_value)로 변환.

    변환 우선순위:
      1. ast.literal_eval — tuple/list/dict/bool/int/float/str 리터럴 처리
      2. 실패 시 str 그대로 반환

    Args:
        raw: "k_value=0.5", "ema_periods=(5,20,40)", "enable_long=True" 등

    Returns:
        (key, typed_value) 튜플

    Raises:
        ValueError: ``=`` 구분자가 없거나 key가 비어있는 경우
    """
    if "=" not in raw:
        raise ValueError(f"--param 형식 오류: '=' 구분자가 없습니다. 예) --param k_value=0.5  (입력값: {raw!r})")

    key, _, value_str = raw.partition("=")
    key = key.strip()
    value_str = value_str.strip()

    if not key:
        raise ValueError(f"--param 형식 오류: key가 비어있습니다. 예) --param k_value=0.5  (입력값: {raw!r})")

    try:
        typed: object = ast.literal_eval(value_str)
    except (ValueError, SyntaxError):
        typed = value_str  # str 그대로

    return key, typed


def parse_param_overrides(raws: list[str]) -> dict[str, object]:
    """여러 --param 값을 dict로 합산.

    Args:
        raws: ["k_value=0.5", "ma_period=20"] 등

    Returns:
        {"k_value": 0.5, "ma_period": 20} 형태의 dict
    """
    result: dict[str, object] = {}
    for raw in raws:
        key, value = parse_param_override(raw)
        result[key] = value
    return result


def merge_params(default_params: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    """default_params를 복사 후 overrides로 덮어씌운다.

    spec.default_params에 없는 키도 허용(전략 params에 존재한다고 가정).

    Args:
        default_params: StrategySpec.default_params
        overrides: CLI --param으로 받은 override dict

    Returns:
        병합된 params dict
    """
    merged = dict(default_params)
    merged.update(overrides)
    return merged


# ---------------------------------------------------------------------------
# Sizer 라벨 파생
# ---------------------------------------------------------------------------

def derive_sizer_label(spec_sizer: SizerConfig | None, manages_own_sizing: bool, default_cli_percent: int) -> str:
    """StrategySpec에서 사람이 읽기 좋은 sizer 라벨을 파생한다.

    Args:
        spec_sizer: StrategySpec.default_sizer (None이면 CLI 기본값 사용)
        manages_own_sizing: StrategySpec.manages_own_sizing
        default_cli_percent: CLI 기본 percent 값 (manages_own_sizing=False & spec_sizer=None 시)

    Returns:
        사람이 읽기 좋은 sizer 라벨 문자열
    """
    if manages_own_sizing:
        return "self-managed"

    cfg = spec_sizer
    if cfg is None:
        return f"percent({default_cli_percent})"

    class_name = cfg.sizer_class.__name__
    if "PercentSizer" in class_name:
        pct = cfg.params.get("percents", "?")
        return f"percent({pct})"
    if "AllInSizer" in class_name:
        return "all-in"
    if "FixedSize" in class_name:
        stake = cfg.params.get("stake", "?")
        return f"fixed({stake})"
    # custom sizer: 클래스명 축약
    return class_name


# ---------------------------------------------------------------------------
# 비교표 포맷터
# ---------------------------------------------------------------------------

@dataclass
class ComparisonRow:
    """비교표 한 행"""

    strategy_name: str
    timeframe: str
    sizer_label: str
    total_return_pct: float
    cagr_pct: float | None
    max_drawdown_pct: float | None
    sharpe_ratio: float | None
    win_rate_pct: float | None
    total_trades: int
    period_days: int | None
    bust: bool = field(default=False)

    @classmethod
    def from_result(
        cls,
        result: BacktestResult,
        timeframe: str,
        sizer_label: str = "",
    ) -> ComparisonRow:
        """BacktestResult로부터 ComparisonRow 생성."""
        return cls(
            strategy_name=result.strategy_name,
            timeframe=timeframe,
            sizer_label=sizer_label,
            total_return_pct=result.total_return_pct,
            cagr_pct=result.cagr_pct,
            max_drawdown_pct=result.max_drawdown_pct,
            sharpe_ratio=result.sharpe_ratio,
            win_rate_pct=result.win_rate_pct,
            total_trades=result.total_trades,
            period_days=result.period_days,
            bust=is_bust(result.final_value, result.total_return_pct),
        )


_PCT_CELL_MAX_LEN: int = 12  # 퍼센트 셀 최대 글자 수 (컬럼 폭 폭발 방지)
_BUST_LABEL: str = "청산/비정상"  # 비정상 전략 수치 셀 대체 라벨


def _fmt_pct(val: float | None, decimals: int = 2) -> str:
    """수익률 등 퍼센트 값을 포맷한다. 비현실적으로 큰 값은 축약 표기."""
    if val is None:
        return "N/A"
    if not math.isfinite(val):
        return ">1e6%" if val > 0 else "<-1e6%"
    # 절댓값이 임계치 초과 시 축약
    if abs(val) > _BUST_RETURN_THRESHOLD:
        return ">1e6%" if val > 0 else "<-1e6%"
    formatted = f"{val:.{decimals}f}%"
    # 포맷 후에도 폭 초과 방지 (이론상 threshold 체크로 커버되지만 방어)
    if len(formatted) > _PCT_CELL_MAX_LEN:
        return ">1e6%" if val > 0 else "<-1e6%"
    return formatted


def _fmt_float(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    if not math.isfinite(val):
        return "N/A"
    return f"{val:.{decimals}f}"


def _fmt_int(val: int | None) -> str:
    if val is None:
        return "N/A"
    return str(val)


def format_comparison_table(rows: list[ComparisonRow]) -> str:
    """비교표를 사람이 읽기 좋은 정렬된 텍스트로 반환.

    정상 전략은 CAGR 기준 내림차순, 비정상(bust) 전략은 맨 아래.
    외부 라이브러리 없이 순수 Python으로 포맷팅.

    Args:
        rows: ComparisonRow 리스트

    Returns:
        출력 준비된 텍스트 문자열
    """
    if not rows:
        return "(비교할 결과가 없습니다)"

    def _sort_key(r: ComparisonRow) -> tuple[int, float]:
        # bust=True → 그룹 1(맨 아래), bust=False → 그룹 0
        # 정렬은 (그룹 오름차순, 수익률 내림차순)을 동시에 달성하기 위해
        # 그룹 부호를 반전(-group)하여 reverse=True와 조합한다.
        group = 1 if r.bust else 0
        if r.bust:
            return (-group, float("-inf"))
        sort_val = r.cagr_pct if r.cagr_pct is not None else r.total_return_pct
        if not math.isfinite(sort_val):
            return (-group, float("-inf"))
        return (-group, sort_val)

    sorted_rows = sorted(rows, key=_sort_key, reverse=True)

    has_bust = any(r.bust for r in sorted_rows)

    # 컬럼 헤더
    headers = ["전략명", "타임프레임", "Sizer", "수익률%", "CAGR%", "MDD%", "Sharpe", "승률%", "거래수", "기간(일)"]

    # 데이터 문자열 변환: bust 행은 수치 셀을 BUST_LABEL로 대체
    str_rows: list[list[str]] = []
    for r in sorted_rows:
        if r.bust:
            str_rows.append([
                r.strategy_name,
                r.timeframe,
                r.sizer_label,
                _BUST_LABEL,  # 수익률%
                _BUST_LABEL,  # CAGR%
                _BUST_LABEL,  # MDD%
                _BUST_LABEL,  # Sharpe
                _BUST_LABEL,  # 승률%
                _fmt_int(r.total_trades),
                _fmt_int(r.period_days),
            ])
        else:
            str_rows.append([
                r.strategy_name,
                r.timeframe,
                r.sizer_label,
                _fmt_pct(r.total_return_pct),
                _fmt_pct(r.cagr_pct),
                _fmt_pct(r.max_drawdown_pct),
                _fmt_float(r.sharpe_ratio),
                _fmt_pct(r.win_rate_pct),
                _fmt_int(r.total_trades),
                _fmt_int(r.period_days),
            ])

    # 컬럼별 최대 너비
    col_widths = [len(h) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"

    lines = [sep, header_line, sep]
    for row in str_rows:
        line = "|" + "|".join(f" {cell:<{col_widths[i]}} " for i, cell in enumerate(row)) + "|"
        lines.append(line)
    lines.append(sep)
    lines.append("* CAGR 내림차순 정렬. 타임프레임/sizer가 다른 전략은 직접 비교 주의.")
    if has_bust:
        lines.append("⚠ 일부 전략이 비정상 종료(파산/무한손실 추정) — 전략 로직 점검 필요")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV 내보내기
# ---------------------------------------------------------------------------

def results_to_csv_str(results: list[BacktestResult], timeframes: dict[str, str]) -> str:
    """BacktestResult 리스트를 CSV 문자열로 직렬화.

    Args:
        results: 백테스트 결과 리스트
        timeframes: strategy_name → timeframe 매핑

    Returns:
        CSV 문자열 (헤더 포함)
    """
    buf = io.StringIO()
    writer: csv.DictWriter[str] = csv.DictWriter(
        buf,
        fieldnames=[
            "strategy_name", "timeframe", "initial_cash", "final_value",
            "total_return_pct", "cagr_pct", "max_drawdown_pct",
            "sharpe_ratio", "total_trades", "win_rate_pct", "period_days",
            "start_date", "end_date",
        ],
    )
    writer.writeheader()
    for r in results:
        row: dict[str, object] = r.to_dict()
        row["timeframe"] = timeframes.get(r.strategy_name, "unknown")
        # inf/nan 수치는 빈칸으로 정규화 (분석 도구 호환)
        for key in ("total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe_ratio", "win_rate_pct"):
            v = row.get(key)
            if isinstance(v, float) and not math.isfinite(v):
                row[key] = ""
        writer.writerow(row)
    return buf.getvalue()
