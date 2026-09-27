"""Pricing endpoints: versioned per-service/material rates, and the
price-estimate calculation built from them.

Reading a rate and estimating a price are open to any authenticated
caller (a customer getting a quote); setting a rate requires `ADMIN`.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from washy_washy.api.v1.controllers import pricing as pricing_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.pricing import (
    EstimatePriceRequest,
    SetMaterialPricingRequest,
    SetServicePricingRequest,
)

router = APIRouter(tags=["pricing"], dependencies=[Depends(get_current_user)])
_admin_only = Depends(require_role(RoleName.ADMIN.value))


@router.get("/services/{service_id}/pricing", response_model=SuccessResponse)
async def get_service_pricing(
    service_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    rule = await pricing_controller.get_service_pricing(service_id, db_session)
    return SuccessResponse(message="Service pricing", data=rule)


@router.post(
    "/services/{service_id}/pricing",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def set_service_pricing(
    service_id: uuid.UUID,
    request: SetServicePricingRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    rule = await pricing_controller.set_service_pricing(service_id, request, db_session)
    return SuccessResponse(message="Service pricing set", data=rule)


@router.get("/materials/{material_id}/pricing", response_model=SuccessResponse)
async def get_material_pricing(
    material_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    rule = await pricing_controller.get_material_pricing(material_id, db_session)
    return SuccessResponse(message="Material pricing", data=rule)


@router.post(
    "/materials/{material_id}/pricing",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def set_material_pricing(
    material_id: uuid.UUID,
    request: SetMaterialPricingRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    rule = await pricing_controller.set_material_pricing(material_id, request, db_session)
    return SuccessResponse(message="Material pricing set", data=rule)


@router.post("/pricing/estimate", response_model=SuccessResponse)
async def estimate_price(
    request: EstimatePriceRequest, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    breakdown = await pricing_controller.estimate_price(request, db_session)
    return SuccessResponse(message="Price estimate", data=breakdown)
