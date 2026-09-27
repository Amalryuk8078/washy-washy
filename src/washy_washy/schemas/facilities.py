"""Request/response schemas for partner facility and partner-status
endpoints.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from core.models.partner_profile import PartnerStatus


class CreateFacilityRequest(BaseModel):
    service_area_id: uuid.UUID
    name: str
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str
    daily_capacity: Decimal | None = None


class FacilityResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    partner_profile_id: uuid.UUID
    service_area_id: uuid.UUID
    name: str
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    postal_code: str
    country: str
    daily_capacity: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SetFacilityActiveRequest(BaseModel):
    is_active: bool


class UpdatePartnerStatusRequest(BaseModel):
    status: PartnerStatus
