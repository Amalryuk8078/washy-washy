"""Security primitives: password hashing and JWT encode/decode.

This module intentionally stops at primitives. Login flows, refresh-token
rotation, and other authentication *workflows* belong in
``washy_washy.services`` once the authentication phase begins.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from core.config import get_core_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenInvalidError(Exception):
    """Raised by ``decode_token_strict`` for a malformed/unsigned/wrong-
    algorithm token — anything except a plain expiry."""


class TokenExpiredError(Exception):
    """Raised by ``decode_token_strict`` when a token's ``exp`` has passed."""


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_core_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_core_settings()
    return _create_token(
        subject,
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
        {"type": "access", **(extra_claims or {})},
    )


def create_refresh_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_core_settings()
    return _create_token(
        subject,
        timedelta(days=settings.jwt_refresh_token_expire_days),
        {"type": "refresh", **(extra_claims or {})},
    )


def decode_token(token: str) -> dict[str, Any] | None:
    settings = get_core_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def decode_token_strict(token: str) -> dict[str, Any]:
    """Like :func:`decode_token`, but raises instead of returning ``None``
    so a caller (e.g. the auth service/``get_current_user`` dependency)
    can tell an expired token apart from any other invalid one and
    respond with the right error code.
    """

    settings = get_core_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError as exc:
        raise TokenExpiredError from exc
    except JWTError as exc:
        raise TokenInvalidError from exc
