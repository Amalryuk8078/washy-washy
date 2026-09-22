"""Request/response schemas for the authentication endpoints.

``UserResponse`` never includes ``password_hash`` — it is the only shape
of ``User`` that ever leaves this service.
"""

import re
import uuid

from pydantic import BaseModel, field_validator

MIN_PASSWORD_LENGTH = 8

# Deliberately simple, not full RFC 5322: this is a sanity check to catch
# obviously malformed input, not a replacement for actually verifying
# deliverability (which is a later-phase email-verification workflow).
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email_format(value: str) -> str:
    if not _EMAIL_PATTERN.match(value.strip()):
        raise ValueError("Enter a valid email address")
    return value


class RegisterRequest(BaseModel):
    email: str
    phone: str | None = None
    password: str
    first_name: str
    last_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email_format(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email_format(value)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    phone: str | None
    first_name: str
    last_name: str | None
    is_active: bool
    is_verified: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
