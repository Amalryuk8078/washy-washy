"""Request-level orchestration for the pricing endpoints."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.pricing import (
    EstimatePriceRequest,
    MaterialPricingRuleResponse,
    PriceBreakdownResponse,
    PricingRuleResponse,
    SetMaterialPricingRequest,
    SetServicePricingRequest,
)
from washy_washy.services.pricing_service import PricingService


async def set_service_pricing(
    service_id: uuid.UUID, request: SetServicePricingRequest, db_session: AsyncSession
) -> PricingRuleResponse:
    service = PricingService(db_session)
    rule = await service.set_service_pricing(
        service_id, request.pricing_model, request.base_price, request.unit_price
    )
    await db_session.commit()
    return PricingRuleResponse.model_validate(rule)


async def get_service_pricing(
    service_id: uuid.UUID, db_session: AsyncSession
) -> PricingRuleResponse:
    service = PricingService(db_session)
    rule = await service.get_active_service_pricing(service_id)
    return PricingRuleResponse.model_validate(rule)


async def set_material_pricing(
    material_id: uuid.UUID, request: SetMaterialPricingRequest, db_session: AsyncSession
) -> MaterialPricingRuleResponse:
    service = PricingService(db_session)
    rule = await service.set_material_pricing(material_id, request.price_adjustment)
    await db_session.commit()
    return MaterialPricingRuleResponse.model_validate(rule)


async def get_material_pricing(
    material_id: uuid.UUID, db_session: AsyncSession
) -> MaterialPricingRuleResponse | None:
    service = PricingService(db_session)
    rule = await service.get_active_material_pricing(material_id)
    return MaterialPricingRuleResponse.model_validate(rule) if rule is not None else None


async def estimate_price(
    request: EstimatePriceRequest, db_session: AsyncSession
) -> PriceBreakdownResponse:
    service = PricingService(db_session)
    breakdown = await service.calculate_price(
        service_id=request.service_id,
        material_id=request.material_id,
        quantity=request.quantity,
        weight_kg=request.weight_kg,
        custom_charge=request.custom_charge,
        rush_charge=request.rush_charge,
        delivery_charge=request.delivery_charge,
        tax=request.tax,
        discount=request.discount,
    )
    return PriceBreakdownResponse(
        base=breakdown.base,
        material_adjustment=breakdown.material_adjustment,
        care_adjustment=breakdown.care_adjustment,
        quantity_charge=breakdown.quantity_charge,
        rush_charge=breakdown.rush_charge,
        delivery_charge=breakdown.delivery_charge,
        tax=breakdown.tax,
        discount=breakdown.discount,
        subtotal=breakdown.subtotal,
        total=breakdown.total,
        pricing_rule_id=breakdown.pricing_rule_id,
        material_pricing_rule_id=breakdown.material_pricing_rule_id,
    )
