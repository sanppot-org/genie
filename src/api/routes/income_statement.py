"""손익계산서(매출·영업이익·순이익) 동기화/조회 API."""
# ruff: noqa: B008

from dataclasses import asdict

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.api.schemas import (
    GenieResponse,
    IncomeStatementPoint,
    IncomeStatementSeriesResponse,
    SyncFinancialsResponse,
)
from src.container import ApplicationContainer
from src.providers.kis_income_statement_client import PERIOD_ANNUAL, PERIOD_QUARTER
from src.service.income_statement_service import IncomeStatementPointData, IncomeStatementService
from src.service.income_statement_sync_service import IncomeStatementSyncService

router = APIRouter(tags=["financials"])

_PERIOD_MAP = {"annual": PERIOD_ANNUAL, "quarter": PERIOD_QUARTER}


def _to_point(p: IncomeStatementPointData) -> IncomeStatementPoint:
    """가공 데이터(Decimal) → 응답 스키마(float, 친화적 필드명)."""
    def f(v: object) -> float | None:
        return float(v) if v is not None else None  # type: ignore[arg-type]

    return IncomeStatementPoint(
        stac_yymm=p.stac_yymm,
        revenue=f(p.sale_account),
        cost_of_sales=f(p.sale_cost),
        gross_profit=f(p.sale_totl_prfi),
        operating_profit=f(p.bsop_prti),
        ordinary_profit=f(p.op_prfi),
        net_income=f(p.thtr_ntin),
        eps=p.eps,
        per=p.per,
        dps=p.dps,
        div=p.div,
        price=p.price,
        is_estimate=p.is_estimate,
    )


@router.get("/financials", response_model=GenieResponse[IncomeStatementSeriesResponse])
@inject
def get_financials(
        ticker: str = Query(min_length=1, max_length=20, description="ticker 코드"),
        period: str = Query(default="annual", pattern=r"^(annual|quarter)$"),
        single: bool = Query(default=False, description="분기 단일환산(quarter 전용)"),
        service: IncomeStatementService = Depends(Provide[ApplicationContainer.income_statement_service]),
) -> GenieResponse[IncomeStatementSeriesResponse]:
    """종목별 손익계산서 시계열 (stac_yymm 오름차순). 종목 미발견 시 404."""
    period_type = _PERIOD_MAP[period]
    single_quarter = single and period_type == PERIOD_QUARTER
    t, points = service.get_time_series(ticker, period_type, single_quarter)
    return GenieResponse(
        data=IncomeStatementSeriesResponse(
            ticker=t.ticker,
            name=t.name,
            period_type=period_type,
            single_quarter=single_quarter,
            points=[_to_point(p) for p in points],
        )
    )


@router.get("/financials/estimates", response_model=GenieResponse[IncomeStatementSeriesResponse])
@inject
def get_financial_estimates(
        ticker: str = Query(min_length=1, max_length=20, description="ticker 코드"),
        service: IncomeStatementService = Depends(Provide[ApplicationContainer.income_statement_service]),
) -> GenieResponse[IncomeStatementSeriesResponse]:
    """종목별 연간 컨센서스 추정행만 반환(확정행 제외, 오름차순). 종목 미발견 시 404.

    확정 시계열(`/financials`)과 분리된 별도 엔드포인트 — 예상은 KIS 라이브 조회가 필요해 점검 중
    지연·실패할 수 있으므로, 프론트가 이 조회를 병렬로 수행해 확정 표를 막지 않게 한다. 추정치는
    연간만 존재하므로 period 파라미터가 없다. 미커버/조회실패 종목은 points=[] (예상행 없음).
    """
    t, points = service.get_annual_estimates(ticker)
    return GenieResponse(
        data=IncomeStatementSeriesResponse(
            ticker=t.ticker,
            name=t.name,
            period_type=PERIOD_ANNUAL,
            single_quarter=False,
            points=[_to_point(p) for p in points],
        )
    )


@router.post("/financials/sync/kr-stock", response_model=GenieResponse[SyncFinancialsResponse])
@inject
def sync_kr_stock_financials(
        service: IncomeStatementSyncService = Depends(Provide[ApplicationContainer.income_statement_sync_service]),
) -> GenieResponse[SyncFinancialsResponse]:
    """증분 수동 동기화(이미 최신 분기 커버 종목은 skip). 대량 초기 적재는 백필 스크립트 사용."""
    result = service.sync(skip_current=True)
    return GenieResponse(data=SyncFinancialsResponse(**asdict(result)))
