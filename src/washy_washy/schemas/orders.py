"""Request/response schemas for the order endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from core.models.order import OrderStatus

ZERO = Decimal("0")


class OrderItemCreateRequest(BaseModel):
    service_id: uuid.UUID
    declared_material_id: uuid.UUID
    declared_quantity: int | None = None
    declared_weight_kg: Decimal | None = None


class CreateOrderRequest(BaseModel):
    pickup_address_id: uuid.UUID
    delivery_address_id: uuid.UUID
    items: list[OrderItemCreateRequest]
    rush_charge: Decimal = ZERO
    delivery_charge: Decimal = ZERO
    tax: Decimal = ZERO
    discount: Decimal = ZERO


class OrderItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    order_id: uuid.UUID
    service_id: uuid.UUID
    declared_material_id: uuid.UUID
    verified_material_id: uuid.UUID | None
    declared_quantity: int | None
    declared_weight_kg: Decimal | None
    verified_quantity: int | None
    verified_weight_kg: Decimal | None
    estimated_pricing_rule_id: uuid.UUID | None
    estimated_material_pricing_rule_id: uuid.UUID | None
    estimated_line_total: Decimal | None
    final_pricing_rule_id: uuid.UUID | None
    final_material_pricing_rule_id: uuid.UUID | None
    final_line_total: Decimal | None
    condition_notes: str | None
    damage_reported: bool
    created_at: datetime
    updated_at: datetime


class OrderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    customer_id: uuid.UUID
    service_area_id: uuid.UUID
    pickup_address_id: uuid.UUID
    delivery_address_id: uuid.UUID
    pickup_slot_id: uuid.UUID | None
    delivery_slot_id: uuid.UUID | None
    assigned_facility_id: uuid.UUID | None
    pickup_operator_user_id: uuid.UUID | None
    delivery_operator_user_id: uuid.UUID | None
    status: str
    estimated_total: Decimal
    final_total: Decimal | None
    created_at: datetime
    updated_at: datetime


class OrderWithItemsResponse(OrderResponse):
    items: list[OrderItemResponse] = []


class TransitionOrderRequest(BaseModel):
    to_status: OrderStatus
    reason: str | None = None


class SchedulePickupRequest(BaseModel):
    pickup_slot_id: uuid.UUID
    capacity_used: Decimal


class ItemizeOrderItemRequest(BaseModel):
    verified_material_id: uuid.UUID | None = None
    verified_quantity: int | None = None
    verified_weight_kg: Decimal | None = None
    condition_notes: str | None = None
    damage_reported: bool | None = None


class FinalizePriceRequest(BaseModel):
    rush_charge: Decimal = ZERO
    delivery_charge: Decimal = ZERO
    tax: Decimal = ZERO
    discount: Decimal = ZERO


class OrderStatusHistoryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    order_id: uuid.UUID
    from_status: str | None
    to_status: str
    changed_by_user_id: uuid.UUID | None
    changed_by_role: str | None
    reason: str | None
    extra_data: dict | None = None
    created_at: datetime


class AssignFacilityRequest(BaseModel):
    facility_id: uuid.UUID
    reason: str | None = None


class AssignOperatorRequest(BaseModel):
    operator_user_id: uuid.UUID
    reason: str | None = None


class OrderAssignmentHistoryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    order_id: uuid.UUID
    assignment_role: str
    previous_assignee_id: uuid.UUID | None
    new_assignee_id: uuid.UUID | None
    changed_by_user_id: uuid.UUID | None
    reason: str | None
    created_at: datetime
