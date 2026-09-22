"""Integration tests for the Phase 2 authentication flow — registration,
login, refresh, and the ``get_current_user`` dependency — against a real
PostgreSQL database. Requires a migrated DB (``alembic upgrade head``);
see tests/integration/conftest.py's ``db_session`` fixture, which skips
cleanly when one isn't available.

``get_current_user`` is exercised by calling it directly as a plain
async function (passing constructed credentials/session) rather than
over HTTP — Phase 2 deliberately has no protected route yet to hang an
end-to-end HTTP test off of; that's exactly what it's for.
"""

import uuid

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from core.exceptions import ConflictException, UnauthorizedException
from core.security.security import create_access_token, create_refresh_token
from washy_washy.dependencies.auth import get_current_user
from washy_washy.schemas.auth import UserResponse
from washy_washy.services.auth_service import AuthService


def _unique_email() -> str:
    return f"user-{uuid.uuid4()}@example.com"


@pytest.mark.asyncio
async def test_register_success(db_session) -> None:
    user = await AuthService(db_session).register(
        email=_unique_email(), password="longenough1", first_name="Test"
    )

    assert isinstance(user.id, uuid.UUID)
    assert user.password_hash != "longenough1"
    assert user.is_active is True
    assert user.is_verified is False


@pytest.mark.asyncio
async def test_registered_user_response_excludes_password_hash(db_session) -> None:
    user = await AuthService(db_session).register(
        email=_unique_email(), password="longenough1", first_name="Test"
    )

    dumped = UserResponse.model_validate(user).model_dump()

    assert "password_hash" not in dumped
    assert "password" not in dumped


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(db_session) -> None:
    email = _unique_email()
    service = AuthService(db_session)
    await service.register(email=email, password="longenough1", first_name="Test")

    with pytest.raises(ConflictException):
        await service.register(email=email.upper(), password="anotherpass1", first_name="Test2")


@pytest.mark.asyncio
async def test_register_duplicate_phone_rejected(db_session) -> None:
    phone = f"+1{uuid.uuid4().int % 10_000_000_000:010d}"
    service = AuthService(db_session)
    await service.register(
        email=_unique_email(), password="longenough1", first_name="Test", phone=phone
    )

    with pytest.raises(ConflictException):
        await service.register(
            email=_unique_email(), password="anotherpass1", first_name="Test2", phone=phone
        )


@pytest.mark.asyncio
async def test_login_success_issues_distinct_access_and_refresh_tokens(db_session) -> None:
    email = _unique_email()
    password = "longenough1"
    await AuthService(db_session).register(email=email, password=password, first_name="Test")

    user, tokens = await AuthService(db_session).login(email=email, password=password)

    assert user.email == email.lower()
    assert tokens.access_token != tokens.refresh_token


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(db_session) -> None:
    email = _unique_email()
    await AuthService(db_session).register(
        email=email, password="correct-password1", first_name="Test"
    )

    with pytest.raises(UnauthorizedException):
        await AuthService(db_session).login(email=email, password="wrong-password1")


@pytest.mark.asyncio
async def test_login_nonexistent_user_rejected(db_session) -> None:
    with pytest.raises(UnauthorizedException):
        await AuthService(db_session).login(email=_unique_email(), password="whatever123")


@pytest.mark.asyncio
async def test_login_inactive_user_rejected(db_session) -> None:
    email = _unique_email()
    password = "longenough1"
    user = await AuthService(db_session).register(email=email, password=password, first_name="Test")
    user.is_active = False
    await db_session.flush()

    with pytest.raises(UnauthorizedException):
        await AuthService(db_session).login(email=email, password=password)


@pytest.mark.asyncio
async def test_refresh_issues_new_access_token(db_session) -> None:
    email = _unique_email()
    password = "longenough1"
    await AuthService(db_session).register(email=email, password=password, first_name="Test")
    _, tokens = await AuthService(db_session).login(email=email, password=password)

    new_access_token = await AuthService(db_session).refresh(tokens.refresh_token)

    assert isinstance(new_access_token, str)
    assert new_access_token != tokens.refresh_token


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(db_session) -> None:
    email = _unique_email()
    password = "longenough1"
    await AuthService(db_session).register(email=email, password=password, first_name="Test")
    _, tokens = await AuthService(db_session).login(email=email, password=password)

    with pytest.raises(UnauthorizedException):
        await AuthService(db_session).refresh(tokens.access_token)


@pytest.mark.asyncio
async def test_get_current_user_resolves_from_valid_access_token(db_session) -> None:
    user = await AuthService(db_session).register(
        email=_unique_email(), password="longenough1", first_name="Test"
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user.id))
    )

    resolved = await get_current_user(credentials=credentials, db_session=db_session)

    assert resolved.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_missing_header_rejected(db_session) -> None:
    with pytest.raises(UnauthorizedException):
        await get_current_user(credentials=None, db_session=db_session)


@pytest.mark.asyncio
async def test_get_current_user_rejects_refresh_token(db_session) -> None:
    user = await AuthService(db_session).register(
        email=_unique_email(), password="longenough1", first_name="Test"
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_refresh_token(str(user.id))
    )

    with pytest.raises(UnauthorizedException):
        await get_current_user(credentials=credentials, db_session=db_session)


@pytest.mark.asyncio
async def test_get_current_user_rejects_malformed_token(db_session) -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")

    with pytest.raises(UnauthorizedException):
        await get_current_user(credentials=credentials, db_session=db_session)


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_user(db_session) -> None:
    user = await AuthService(db_session).register(
        email=_unique_email(), password="longenough1", first_name="Test"
    )
    user.is_active = False
    await db_session.flush()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user.id))
    )

    with pytest.raises(UnauthorizedException):
        await get_current_user(credentials=credentials, db_session=db_session)
