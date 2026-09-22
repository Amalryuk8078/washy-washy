"""Offline (no database) tests for Phase 2 authentication primitives:
password hashing, JWT issuance/decoding, and the auth request/response
schemas' own validation.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt as jose_jwt
from pydantic import ValidationError

from core.config import get_core_settings
from core.security.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    decode_token_strict,
    hash_password,
    verify_password,
)
from washy_washy.schemas.auth import LoginRequest, RegisterRequest, UserResponse


def test_hash_password_differs_from_raw_and_verifies() -> None:
    raw = "correct horse battery staple"
    hashed = hash_password(raw)

    assert hashed != raw
    assert verify_password(raw, hashed)
    assert not verify_password("wrong password", hashed)


def test_access_and_refresh_tokens_carry_distinct_type_claim() -> None:
    subject = str(uuid.uuid4())

    access_payload = decode_token_strict(create_access_token(subject))
    refresh_payload = decode_token_strict(create_refresh_token(subject))

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == subject
    assert refresh_payload["sub"] == subject


def test_decode_token_strict_rejects_garbage_token() -> None:
    with pytest.raises(TokenInvalidError):
        decode_token_strict("not.a.jwt")


def test_decode_token_strict_rejects_expired_token() -> None:
    settings = get_core_settings()
    now = datetime.now(UTC)
    expired = jose_jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(TokenExpiredError):
        decode_token_strict(expired)


def test_decode_token_strict_rejects_wrong_signature() -> None:
    token = jose_jwt.encode(
        {"sub": "x", "type": "access"}, "a-different-secret-entirely", algorithm="HS256"
    )

    with pytest.raises(TokenInvalidError):
        decode_token_strict(token)


@pytest.mark.parametrize("password", ["", "short1", "1234567"])
def test_register_request_rejects_short_or_empty_password(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", password=password, first_name="Test")


def test_register_request_accepts_valid_password() -> None:
    request = RegisterRequest(email="user@example.com", password="longenough1", first_name="Test")
    assert request.password == "longenough1"


@pytest.mark.parametrize("email", ["not-an-email", "missing-at.example.com", "@example.com"])
def test_register_request_rejects_malformed_email(email: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email=email, password="longenough1", first_name="Test")


def test_login_request_rejects_malformed_email() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="whatever")


def test_user_response_has_no_password_field() -> None:
    assert "password_hash" not in UserResponse.model_fields
    assert "password" not in UserResponse.model_fields
