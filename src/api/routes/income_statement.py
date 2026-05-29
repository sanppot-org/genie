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


@router.post("/financials/sync/kr-stock", response_model=GenieResponse[SyncFinancialsResponse])
@inject
def sync_kr_stock_financials(
        service: IncomeStatementSyncService = Depends(Provide[ApplicationContainer.income_statement_sync_service]),
) -> GenieResponse[SyncFinancialsResponse]:
    """증분 수동 동기화(이미 최신 분기 커버 종목은 skip). 대량 초기 적재는 백필 스크립트 사용."""
    result = service.sync(skip_current=True)
    return GenieResponse(data=SyncFinancialsResponse(**asdict(result)))
