"""Request/response schemas for the address endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


def _validate_latitude(value: Decimal | None) -> Decimal | None:
    if value is not None and not (-90 <= value <= 90):
        raise ValueError("latitude must be between -90 and 90")
    return value


def _validate_longitude(value: Decimal | None) -> Decimal | None:
    if value is not None and not (-180 <= value <= 180):
        raise ValueError("longitude must be between -180 and 180")
    return value


class CreateAddressRequest(BaseModel):
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str
    label: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    is_default: bool = False

    @field_validator("latitude")
    @classmethod
    def check_latitude(cls, value: Decimal | None) -> Decimal | None:
        return _validate_latitude(value)

    @field_validator("longitude")
    @classmethod
    def check_longitude(cls, value: Decimal | None) -> Decimal | None:
        return _validate_longitude(value)


class UpdateAddressRequest(BaseModel):
    """Every field is optional and ``None`` means "leave unchanged" —
    see ``AddressService.update_address``'s docstring for the resulting
    limitation (can't explicitly clear ``address_line_2``).
    """

    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    label: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    @field_validator("latitude")
    @classmethod
    def check_latitude(cls, value: Decimal | None) -> Decimal | None:
        return _validate_latitude(value)

    @field_validator("longitude")
    @classmethod
    def check_longitude(cls, value: Decimal | None) -> Decimal | None:
        return _validate_longitude(value)


class AddressResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    postal_code: str
    country: str
    latitude: Decimal | None
    longitude: Decimal | None
    label: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
