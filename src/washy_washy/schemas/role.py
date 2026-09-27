"""Request/response schemas for the admin role-management endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class GrantRoleRequest(BaseModel):
    role_name: str


class RoleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
