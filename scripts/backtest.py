"""범용 백테스트 CLI — 여러 전략을 동일 조건으로 비교.

사용 예시:
    # 단일 전략 (기본: 주식 일봉)
    ENV_PROFILE=local uv run python scripts/backtest.py --ticker TQQQ --strategy volatility_breakout --start 20200101 --end 20241231

    # 다중 전략 (콤마 구분)
    ENV_PROFILE=local uv run python scripts/backtest.py --ticker TQQQ --strategy buy_and_hold,volatility_breakout,simple --start 20200101 --end 20241231

    # 전략 전체 비교
    ENV_PROFILE=local uv run python scripts/backtest.py --ticker TQQQ --all --start 20200101 --end 20241231

    # 파라미터 override + CSV 저장
    ENV_PROFILE=local uv run python scripts/backtest.py --ticker TQQQ --strategy volatility_breakout --start 20200101 --end 20241231 --param k_value=0.3 --csv /tmp/result.csv

    # 초기 자본·수수료 설정
    ENV_PROFILE=local uv run python scripts/backtest.py --ticker TQQQ --all --start 20200101 --end 20241231 --initial-cash 5000000 --commission 0.0005

    # 전략 목록 확인
    ENV_PROFILE=local uv run python scripts/backtest.py --list-strategies

    # 암호화폐 일봉 (크립토 테이블 사용)
    ENV_PROFILE=local uv run python scripts/backtest.py --ticker BTC --asset crypto --strategy buy_and_hold --start 20200101 --end 20241231

선행 조건:
    해당 티커의 캔들 데이터가 DB에 백필되어 있어야 합니다.
    (주식 일봉: register_us_tickers.py + backfill_us_daily_candles.py, 분/시간봉: 별도 backfill 스크립트)
"""

import argparse
from datetime import datetime
import logging
import sys

from src.backtest.cli import (
    ComparisonRow,
    derive_sizer_label,
    format_comparison_table,
    parse_param_overrides,
    results_to_csv_str,
)
from src.backtest.registry import get_strategy, list_strategies
from src.service.backtest_service import _DEFAULT_PERCENT as _DEFAULT_CLI_PERCENT
from src.service.backtest_service import _load_candles_df, _run_single_strategy

logger = logging.getLogger(__name__)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="범용 백테스트 CLI — 여러 전략을 동일 초기 자본으로 비교합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--ticker", default=None, help="종목 코드 (예: TQQQ, 005930)")
    parser.add_argument(
        "--asset",
        choices=["stock", "crypto"],
        default="stock",
        help="자산 유형 (기본: stock). stock+1d → StockDailyCandleRepository(수정주가), crypto+1d → CandleDailyRepository",
    )
    parser.add_argument("--list-strategies", action="store_true", help="레지스트리 전략명·설명·타임프레임 출력 후 종료")

    strategy_group = parser.add_mutually_exclusive_group()
    strategy_group.add_argument(
        "--strategy",
        metavar="NAME[,NAME...]",
        help="실행할 전략 이름. 콤마로 구분하여 여러 개 지정 가능. (예: buy_and_hold,volatility_breakout)",
    )
    strategy_group.add_argument("--all", action="store_true", help="레지스트리에 등록된 모든 전략 실행")

    parser.add_argument("--start", default=None, help="시작일 YYYYMMDD (기본: 전체 데이터)")
    parser.add_argument("--end", default=None, help="종료일 YYYYMMDD (기본: 전체 데이터)")
    parser.add_argument("--initial-cash", type=float, default=10_000_000.0, help="초기 자본 (기본: 10,000,000)")
    parser.add_argument("--commission", type=float, default=0.0005, help="수수료율 (기본: 0.0005 = 0.05%%)")
    parser.add_argument("--slippage", type=float, default=0.0, help="슬리피지율 (기본: 0.0)")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        dest="params",
        metavar="KEY=VALUE",
        help="전략 파라미터 override. 반복 가능. tuple은 ast.literal_eval로 파싱. (예: --param k_value=0.3 --param ema_periods=\"(5,20,40)\")",
    )
    parser.add_argument("--csv", default=None, metavar="PATH", help="비교 결과를 CSV로 저장할 경로 (선택)")
    parser.add_argument("--verbose", action="store_true", help="전략 내부 로그(print) 그대로 출력 (기본: 억제)")
    return parser


def _resolve_specs(args: argparse.Namespace) -> list:
    """CLI 인수로부터 실행할 StrategySpec 목록 반환."""
    if args.all:
        return [get_strategy(name) for name in list_strategies()]

    names = [n.strip() for n in args.strategy.split(",") if n.strip()]
    specs = []
    for name in names:
        try:
            specs.append(get_strategy(name))
        except ValueError as e:
            logger.error("전략 조회 실패: %s", e)
            sys.exit(1)
    return specs


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # --list-strategies: 전략 목록 출력 후 종료
    if args.list_strategies:
        print(f"{'전략명':<25} {'타임프레임':<10} 설명")
        print("-" * 70)
        for name in list_strategies():
            spec = get_strategy(name)
            print(f"{spec.name:<25} {spec.timeframe:<10} {spec.description}")
        sys.exit(0)

    # --ticker 필수 (--list-strategies 이외)
    if not args.ticker:
        parser.error("--ticker 는 필수입니다 (--list-strategies 제외)")

    # --strategy 또는 --all 중 하나는 필수
    if not args.strategy and not args.all:
        parser.error("--strategy NAME 또는 --all 중 하나는 필수입니다")

    # 날짜 파싱 + 검증
    start_dt: datetime | None = None
    end_dt: datetime | None = None
    try:
        if args.start:
            start_dt = datetime.strptime(args.start, "%Y%m%d")
        if args.end:
            end_dt = datetime.strptime(args.end, "%Y%m%d")
    except ValueError:
        logger.error("날짜는 YYYYMMDD 형식으로 입력하세요. 예) 20200101")
        sys.exit(1)

    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        logger.error("종료일(%s)이 시작일(%s)보다 앞설 수 없습니다.", args.end, args.start)
        sys.exit(1)

    # --param 파싱
    try:
        param_overrides = parse_param_overrides(args.params)
    except ValueError as e:
        logger.error("%s", e)
        sys.exit(1)

    # 전략 목록 확정
    specs = _resolve_specs(args)
    if not specs:
        logger.error("실행할 전략이 없습니다.")
        sys.exit(1)

    # --param은 단일 전략에서만 허용
    if param_overrides and len(specs) > 1:
        logger.error("--param은 단일 전략(--strategy NAME 하나)에서만 사용하세요. 현재 대상 전략: %s", [s.name for s in specs])
        sys.exit(1)

    logger.info("=== 백테스트 시작 ===")
    logger.info("티커: %s | 자산: %s | 전략: %s | 기간: %s ~ %s", args.ticker, args.asset, [s.name for s in specs], args.start or "전체", args.end or "전체")
    logger.info("초기 자본: %.0f | 수수료: %.4f | 슬리피지: %.4f", args.initial_cash, args.commission, args.slippage)

    # 타임프레임 혼합 경고 (실행 전 — 표 위에 위치하도록 여기서 출력)
    timeframes_in_specs = {s.timeframe for s in specs}
    if len(timeframes_in_specs) > 1:
        logger.warning("주의: 비교 대상 전략들의 타임프레임이 다릅니다 (%s). 타임프레임이 다른 전략은 직접 비교에 주의하세요.", timeframes_in_specs)

    # ── 1단계: DB 세션 안에서 캔들 로드 + DataFrame 변환만 수행 ──────────────
    import pandas as pd

    from src.container import ApplicationContainer
    from src.database.ticker_repository import TickerRepository

    database = ApplicationContainer().database()
    # (spec.name → DataFrame) 맵
    spec_dfs: dict[str, pd.DataFrame] = {}

    # 티커 조회는 별도 세션으로 먼저 수행한다.
    with database.session_scope() as session:
        ticker_obj = TickerRepository(session).find_by_ticker(args.ticker)
        if ticker_obj is None or ticker_obj.id is None:
            logger.error("티커 미등록: %s — ticker_repository에 먼저 등록하세요.", args.ticker)
            sys.exit(1)
        ticker_id: int = ticker_obj.id

    # 전략별로 독립 세션을 열어 캔들을 로드한다.
    # DB 예외(테이블 없음 등)가 발생하면 해당 세션만 롤백·종료되고
    # 다음 전략은 새 세션으로 안전하게 시도할 수 있다.
    for spec in specs:
        logger.info("--- [%s] 캔들 로드 중 (timeframe=%s, asset=%s) ---", spec.name, spec.timeframe, args.asset)
        try:
            with database.session_scope() as session:
                df, actual_tf = _load_candles_df(spec, ticker_id, start_dt, end_dt, args.asset, session)
            if df.empty:
                logger.warning("[%s] 캔들 데이터 없음 (ticker=%s, timeframe=%s) — 스킵", spec.name, args.ticker, spec.timeframe)
            else:
                spec_dfs[spec.name] = df
        except Exception as exc:
            logger.warning(
                "[%s] 캔들 로드 실패 (ticker=%s, timeframe=%s) — 스킵: %s",
                spec.name,
                args.ticker,
                spec.timeframe,
                exc,
            )

    # ── 2단계: 세션 종료 후 백테스트 실행 (DB 커넥션 비점유) ────────────────
    from src.backtest.result import BacktestResult
    results: list[BacktestResult] = []
    tf_map: dict[str, str] = {}
    sizer_map: dict[str, str] = {}

    for spec in specs:
        spec_df: pd.DataFrame | None = spec_dfs.get(spec.name)
        if spec_df is None:
            continue
        logger.info("--- [%s] 실행 중 ---", spec.name)
        result = _run_single_strategy(
            spec=spec,
            ticker=args.ticker,
            df=spec_df,
            initial_cash=args.initial_cash,
            commission=args.commission,
            slippage=args.slippage,
            param_overrides=param_overrides,
            verbose=args.verbose,
        )
        if result is not None:
            results.append(result)
            tf_map[spec.name] = spec.timeframe
            sizer_map[spec.name] = derive_sizer_label(spec.default_sizer, spec.manages_own_sizing, _DEFAULT_CLI_PERCENT)

    total_specs = len(specs)
    success_count = len(results)
    failed_count = total_specs - success_count

    if not results:
        logger.error("실행 가능한 전략 결과가 없습니다.")
        sys.exit(1)

    # 타임프레임 혼합 경고 (성공 결과 기준 — 표 위에 출력)
    timeframes_used = {tf_map[r.strategy_name] for r in results}
    mixed_tf_warning = len(timeframes_used) > 1

    # 비교표 출력
    comparison_rows = [
        ComparisonRow.from_result(r, tf_map.get(r.strategy_name, "unknown"), sizer_map.get(r.strategy_name, ""))
        for r in results
    ]

    print("\n" + "=" * 70)
    print(f"백테스트 비교 결과 — {args.ticker} ({args.start or '전체'} ~ {args.end or '전체'})")
    print(f"초기자본: {int(args.initial_cash):,} / 수수료: {args.commission} / 슬리피지: {args.slippage}")
    print(f"결과: {total_specs}개 전략 중 {success_count}개 성공" + (f", {failed_count}개 실패" if failed_count else ""))
    if mixed_tf_warning:
        print(f"[주의] 타임프레임 혼합: {timeframes_used} — 직접 비교 시 유의하세요.")
    print("=" * 70)
    print(format_comparison_table(comparison_rows))

    # CSV 저장
    if args.csv:
        try:
            csv_str = results_to_csv_str(results, tf_map)
            with open(args.csv, "w", encoding="utf-8", newline="") as f:
                f.write(csv_str)
            logger.info("CSV 저장 완료: %s", args.csv)
        except OSError as e:
            logger.error("CSV 저장 실패 (결과는 이미 출력됨): %s", e)


if __name__ == "__main__":
    main()
