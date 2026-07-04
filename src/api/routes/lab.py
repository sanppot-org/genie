"""Lab API — 백테스트 실행 + US 데이터 관리 (종목 등록·캔들 백필) 엔드포인트."""
# ruff: noqa: B008

from dataclasses import asdict
from datetime import date, datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import (
    BacktestBenchmark,
    BacktestEquityPoint,
    BacktestRunItem,
    BacktestRunRequest,
    BacktestRunResponse,
    CorrelationRequest,
    CorrelationResponse,
    GenieResponse,
    StrategyInfo,
    UsBackfillRequest,
    UsBackfillResult,
    UsRegisterRequest,
    UsRegisterResult,
    UsTickerInfo,
)
from src.backtest.result import EquityPoint
from src.container import ApplicationContainer
from src.service.backtest_service import BacktestService, BenchmarkResult
from src.service.correlation_service import CorrelationService
from src.service.us_stock_daily_candle_service import UsStockDailyCandleService
from src.service.us_stock_ticker_service import UsStockTickerService

router = APIRouter(tags=["lab"])


def _to_equity_points(curve: list[EquityPoint] | None) -> list[BacktestEquityPoint] | None:
    """도메인 EquityPoint 리스트 → API 스키마 변환. None은 그대로 통과."""
    if curve is None:
        return None
    return [BacktestEquityPoint(date=p.date, return_pct=p.return_pct, drawdown_pct=p.drawdown_pct) for p in curve]


def _to_benchmark(bench: BenchmarkResult | None) -> BacktestBenchmark | None:
    """도메인 BenchmarkResult → API 스키마 변환 (곡선 + 요약 지표). None은 그대로 통과."""
    if bench is None:
        return None
    return BacktestBenchmark(
        curve=_to_equity_points(bench.curve) or [],
        total_return_pct=bench.total_return_pct,
        cagr_pct=bench.cagr_pct,
        max_drawdown_pct=bench.max_drawdown_pct,
        sharpe_ratio=bench.sharpe_ratio,
        sortino_ratio=bench.sortino_ratio,
    )


@router.get("/backtest/strategies", response_model=GenieResponse[list[StrategyInfo]])
@inject
def get_strategies(
        service: BacktestService = Depends(Provide[ApplicationContainer.backtest_service]),
) -> GenieResponse[list[StrategyInfo]]:
    """레지스트리에 등록된 전략 목록 반환. [{name, timeframe, description, default_params}]"""
    infos = [
        StrategyInfo(
            name=spec.name,
            timeframe=spec.timeframe,
            description=spec.description,
            default_params=dict(spec.default_params),
        )
        for spec in service.list_strategies()
    ]
    return GenieResponse(data=infos)


@router.post("/backtest/run", response_model=GenieResponse[BacktestRunResponse])
@inject
def run_backtest(
        request: BacktestRunRequest,
        service: BacktestService = Depends(Provide[ApplicationContainer.backtest_service]),
) -> GenieResponse[BacktestRunResponse]:
    """백테스트 실행. ticker + 전략 목록 + 기간/자본/수수료 파라미터를 받아 결과 반환.

    - 잘못된 전략명: 400
    - 미등록 티커: 400
    - 데이터 없는 전략: skipped 목록에 포함 (results에서 제외)
    - 실행 예외 전략: failed 목록에 포함
    """
    # param_overrides 다중전략 가드 (CLI 규칙과 동일)
    if request.param_overrides and len(request.strategies) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="param_overrides는 단일 전략 요청에서만 사용할 수 있습니다.",
        )

    # 날짜 파싱
    start: date | None = None
    end: date | None = None
    try:
        if request.start:
            start = datetime.strptime(request.start, "%Y%m%d").date()
        if request.end:
            end = datetime.strptime(request.end, "%Y%m%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="날짜는 YYYYMMDD 형식이어야 합니다.") from None

    if start and end and end < start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="종료일이 시작일보다 앞설 수 없습니다.")

    # 전략명 검증
    try:
        from src.backtest.registry import get_strategy as _gs
        for name in request.strategies:
            _gs(name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    # 실행
    try:
        output = service.run(
            ticker=request.ticker,
            strategy_names=request.strategies,
            start=start,
            end=end,
            initial_cash=request.initial_cash,
            commission=request.commission,
            slippage=request.slippage,
            asset=request.asset,
            param_overrides=request.param_overrides,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    items = [
        BacktestRunItem(
            strategy_name=rr.result.strategy_name,
            timeframe=rr.timeframe,
            initial_cash=rr.result.initial_cash,
            final_value=rr.result.final_value,
            total_return_pct=rr.result.total_return_pct,
            cagr_pct=rr.result.cagr_pct,
            max_drawdown_pct=rr.result.max_drawdown_pct,
            sharpe_ratio=rr.result.sharpe_ratio,
            sortino_ratio=rr.result.sortino_ratio,
            total_trades=rr.result.total_trades,
            win_rate_pct=rr.result.win_rate_pct,
            period_days=rr.result.period_days,
            start_date=rr.result.start_date,
            end_date=rr.result.end_date,
            bust=rr.bust,
            equity_curve=_to_equity_points(rr.result.equity_curve),
        )
        for rr in output.results
    ]
    return GenieResponse(data=BacktestRunResponse(
        results=items,
        skipped=output.skipped,
        failed=output.failed,
        mixed_timeframes=output.mixed_timeframes,
        benchmark=_to_benchmark(output.benchmark),
    ))


@router.post("/correlation/run", response_model=GenieResponse[CorrelationResponse])
@inject
def run_correlation(
        request: CorrelationRequest,
        service: CorrelationService = Depends(Provide[ApplicationContainer.correlation_service]),
) -> GenieResponse[CorrelationResponse]:
    """멀티 티커 상관관계 분석. 기본은 일봉 수익률(pct_change) 피어슨 상관행렬.

    - 티커 2~20개(스키마 검증). 미등록·무데이터 티커는 dropped에 포함.
    - 공통 거래일만 사용(dropna). 결과 행/열 순서는 tickers 배열을 따름.
    """
    start: date | None = None
    end: date | None = None
    try:
        if request.start:
            start = datetime.strptime(request.start, "%Y%m%d").date()
        if request.end:
            end = datetime.strptime(request.end, "%Y%m%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="날짜는 YYYYMMDD 형식이어야 합니다.") from None

    if start and end and end < start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="종료일이 시작일보다 앞설 수 없습니다.")

    try:
        output = service.run(
            tickers=request.tickers,
            start=start,
            end=end,
            asset=request.asset,
            method=request.method,
            return_type=request.return_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return GenieResponse(data=CorrelationResponse(
        tickers=output.tickers,
        matrix=output.matrix,
        observations=output.observations,
        period_start=output.period_start,
        period_end=output.period_end,
        method=output.method,
        return_type=output.return_type,
        dropped=output.dropped,
        warnings=output.warnings,
    ))


@router.post("/us-tickers/register", response_model=GenieResponse[UsRegisterResult])
@inject
def register_us_tickers(
        request: UsRegisterRequest,
        service: UsStockTickerService = Depends(Provide[ApplicationContainer.us_stock_ticker_service]),
) -> GenieResponse[UsRegisterResult]:
    """미국 주식/ETF 종목을 FDR StockListing 기반으로 등록(또는 갱신).

    FDR 목록에 없는 심볼은 skipped_unknown에 집계되고 skipped 배열에 포함됩니다.
    """
    try:
        result = service.register(request.symbols)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return GenieResponse(data=UsRegisterResult(**asdict(result)))


@router.post("/us-candles/backfill", response_model=GenieResponse[UsBackfillResult])
@inject
def backfill_us_candles(
        request: UsBackfillRequest,
        service: UsStockDailyCandleService = Depends(Provide[ApplicationContainer.us_stock_daily_candle_service]),
) -> GenieResponse[UsBackfillResult]:
    """미국 주식 일봉 백필 (심볼 subset 전용).

    종목 수 × 약 0.5초 소요 — 소수 심볼만 권장. start 미지정 시 1990-01-01부터 백필합니다.
    """
    start_date: date | None = None
    if request.start:
        try:
            start_date = datetime.strptime(request.start, "%Y%m%d").date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start는 YYYYMMDD 형식이어야 합니다.") from None

    kwargs: dict[str, object] = {"symbols": request.symbols}
    if start_date is not None:
        kwargs["start"] = start_date

    try:
        result = service.backfill(**kwargs)  # type: ignore[arg-type]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return GenieResponse(data=UsBackfillResult(**asdict(result)))


@router.get("/us-tickers", response_model=GenieResponse[list[UsTickerInfo]])
@inject
def list_us_tickers(
        service: UsStockTickerService = Depends(Provide[ApplicationContainer.us_stock_ticker_service]),
) -> GenieResponse[list[UsTickerInfo]]:
    """등록된 미국 티커(US_STOCK + US_ETF) 목록과 stock_daily_candles 데이터 보유 현황 반환.

    정렬: 봉수 내림차순 → ticker 오름차순.
    """
    summaries = service.list_us_tickers()
    items = [
        UsTickerInfo(
            ticker=s.ticker,
            name=s.name,
            asset_type=s.asset_type,
            exchange=s.exchange,
            candle_count=s.candle_count,
            first_date=s.first_date,
            last_date=s.last_date,
        )
        for s in summaries
    ]
    return GenieResponse(data=items)
