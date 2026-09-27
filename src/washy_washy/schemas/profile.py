"""Request/response schemas for customer/partner profile endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateCustomerProfileRequest(BaseModel):
    display_name: str | None = None


class CustomerProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str | None
    created_at: datetime
    updated_at: datetime


class PartnerProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    business_name: str
    contact_phone: str | None
    status: str
    created_at: datetime
    updated_at: datetime
