"""Request/response schemas for the availability/slot/capacity endpoints."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel


class SetOperatingHoursRequest(BaseModel):
    day_of_week: str
    opening_time: time
    closing_time: time


class OperatingHoursResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    service_area_id: uuid.UUID
    day_of_week: str
    opening_time: time
    closing_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SetPartnerAvailabilityRequest(BaseModel):
    day_of_week: str
    start_time: time
    end_time: time


class PartnerAvailabilityResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    partner_profile_id: uuid.UUID
    day_of_week: str
    start_time: time
    end_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateSlotRequest(BaseModel):
    slot_date: date
    start_time: time
    end_time: time
    capacity_unit: str
    capacity_total: Decimal


class SlotResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    service_area_id: uuid.UUID
    slot_date: date
    start_time: time
    end_time: time
    capacity_unit: str
    capacity_total: Decimal
    capacity_reserved: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BookSlotRequest(BaseModel):
    capacity_used: Decimal


class SlotReservationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    slot_id: uuid.UUID
    customer_user_id: uuid.UUID
    capacity_used: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
