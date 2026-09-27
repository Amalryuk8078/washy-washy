"""Request/response schemas for the catalog endpoints (services,
materials, and their compatibility rows).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateServiceRequest(BaseModel):
    name: str
    description: str | None = None


class ServiceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateMaterialRequest(BaseModel):
    name: str
    description: str | None = None


class MaterialResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UpdateActiveRequest(BaseModel):
    is_active: bool


class SetCompatibilityRequest(BaseModel):
    material_id: uuid.UUID
    care_instructions: str | None = None
    max_temperature_celsius: int | None = None


class ServiceMaterialResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    service_id: uuid.UUID
    material_id: uuid.UUID
    care_instructions: str | None
    max_temperature_celsius: int | None
    created_at: datetime
    updated_at: datetime
