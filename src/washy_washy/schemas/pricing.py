"""Request/response schemas for the pricing endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SetServicePricingRequest(BaseModel):
    pricing_model: str
    base_price: Decimal
    unit_price: Decimal


class SetMaterialPricingRequest(BaseModel):
    price_adjustment: Decimal


class PricingRuleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    service_id: uuid.UUID
    pricing_model: str
    base_price: Decimal
    unit_price: Decimal
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime


class MaterialPricingRuleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    material_id: uuid.UUID
    price_adjustment: Decimal
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime


class EstimatePriceRequest(BaseModel):
    service_id: uuid.UUID
    material_id: uuid.UUID
    quantity: int | None = None
    weight_kg: Decimal | None = None
    custom_charge: Decimal | None = None
    rush_charge: Decimal = Decimal("0")
    delivery_charge: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")


class PriceBreakdownResponse(BaseModel):
    base: Decimal
    material_adjustment: Decimal
    care_adjustment: Decimal
    quantity_charge: Decimal
    rush_charge: Decimal
    delivery_charge: Decimal
    tax: Decimal
    discount: Decimal
    subtotal: Decimal
    total: Decimal
    pricing_rule_id: uuid.UUID
    material_pricing_rule_id: uuid.UUID | None
