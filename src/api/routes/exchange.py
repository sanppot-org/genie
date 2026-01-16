"""Exchange CRUD API 엔드포인트"""
# ruff: noqa: B008

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.api.schemas import ExchangeCreate, ExchangeResponse, ExchangeUpdate, GenieResponse
from src.container import ApplicationContainer
from src.service.exchange_service import ExchangeService

router = APIRouter(tags=["exchanges"])


@router.post("/exchanges", response_model=GenieResponse[ExchangeResponse], status_code=status.HTTP_201_CREATED)
@inject
def create_exchange(
        exchange_in: ExchangeCreate,
        service: ExchangeService = Depends(Provide[ApplicationContainer.exchange_service]),
) -> GenieResponse[ExchangeResponse]:
    """Exchange 생성"""
    exchange = service.create(exchange_in)
    return GenieResponse(data=ExchangeResponse.from_exchange(exchange))


@router.put("/exchanges/{exchange_id}", response_model=GenieResponse[ExchangeResponse])
@inject
def update_exchange(
        exchange_id: int,
        exchange_in: ExchangeUpdate,
        service: ExchangeService = Depends(Provide[ApplicationContainer.exchange_service]),
) -> GenieResponse[ExchangeResponse]:
    """Exchange 수정"""
    exchange = service.update(exchange_id, exchange_in)
    return GenieResponse(data=ExchangeResponse.from_exchange(exchange))


@router.get("/exchanges", response_model=GenieResponse[list[ExchangeResponse]])
@inject
def get_all_exchanges(
        service: ExchangeService = Depends(Provide[ApplicationContainer.exchange_service]),
) -> GenieResponse[list[ExchangeResponse]]:
    """전체 exchange 조회"""
    exchanges = service.get_all()
    return GenieResponse(data=[ExchangeResponse.from_exchange(e) for e in exchanges])


@router.get("/exchanges/{exchange_id}", response_model=GenieResponse[ExchangeResponse])
@inject
def get_exchange(
        exchange_id: int,
        service: ExchangeService = Depends(Provide[ApplicationContainer.exchange_service]),
) -> GenieResponse[ExchangeResponse]:
    """ID로 exchange 조회"""
    exchange = service.get_by_id(exchange_id)
    return GenieResponse(data=ExchangeResponse.from_exchange(exchange))


@router.delete("/exchanges/{exchange_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
def delete_exchange(
        exchange_id: int,
        service: ExchangeService = Depends(Provide[ApplicationContainer.exchange_service]),
) -> None:
    """exchange 삭제 (없으면 무시)"""
    service.delete(exchange_id)
