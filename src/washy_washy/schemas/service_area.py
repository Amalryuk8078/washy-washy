"""Request/response schemas for the service area endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateServiceAreaRequest(BaseModel):
    name: str
    postal_codes: list[str] = []

    @field_validator("postal_codes")
    @classmethod
    def dedupe_postal_codes(cls, value: list[str]) -> list[str]:
        # Preserve order while dropping duplicates -- the DB's unique
        # constraint would reject a literal duplicate anyway, but that's
        # a confusing IntegrityError for what's really just sloppy input.
        seen: set[str] = set()
        deduped = []
        for postal_code in value:
            if postal_code not in seen:
                seen.add(postal_code)
                deduped.append(postal_code)
        return deduped


class ServiceAreaResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
