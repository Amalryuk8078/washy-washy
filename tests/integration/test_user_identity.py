"""Integration tests for User persistence against a real PostgreSQL
database. Requires a migrated DB (``alembic upgrade head``) — see
tests/integration/conftest.py's ``db_session`` fixture, which skips
cleanly when one isn't available.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from core.models.user import User
from core.security.security import hash_password, verify_password
from washy_washy.repositories.user_repo import UserRepository, normalize_email


def _new_user(**overrides) -> User:
    defaults = {
        "email": f"user-{uuid.uuid4()}@example.com",
        "password_hash": "not-a-real-hash",
        "first_name": "Test",
    }
    defaults.update(overrides)
    return User(**defaults)


@pytest.mark.asyncio
async def test_create_user_generates_uuid_and_server_timestamps(db_session) -> None:
    user = await UserRepository(db_session).create(_new_user())

    assert isinstance(user.id, uuid.UUID)
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_create_user_default_lifecycle_flags(db_session) -> None:
    user = await UserRepository(db_session).create(_new_user())

    assert user.is_active is True
    assert user.is_verified is False


@pytest.mark.asyncio
async def test_get_by_id_retrieves_created_user(db_session) -> None:
    repo = UserRepository(db_session)
    created = await repo.create(_new_user())

    fetched = await repo.get_by_id(created.id)

    assert fetched is not None
    assert fetched.email == created.email


@pytest.mark.asyncio
async def test_email_is_normalized_on_write_and_lookup(db_session) -> None:
    repo = UserRepository(db_session)
    raw_email = f"  Amal.{uuid.uuid4()}@Example.COM  "

    created = await repo.create(_new_user(email=raw_email))
    assert created.email == normalize_email(raw_email)

    fetched = await repo.get_by_email(raw_email.upper())
    assert fetched is not None
    assert fetched.id == created.id


@pytest.mark.asyncio
async def test_duplicate_normalized_email_rejected(db_session) -> None:
    repo = UserRepository(db_session)
    email = f"dupe-{uuid.uuid4()}@example.com"
    await repo.create(_new_user(email=email))

    with pytest.raises(IntegrityError):
        await repo.create(_new_user(email=email.upper()))


@pytest.mark.asyncio
async def test_duplicate_phone_rejected(db_session) -> None:
    repo = UserRepository(db_session)
    phone = f"+1{uuid.uuid4().int % 10_000_000_000:010d}"
    await repo.create(_new_user(phone=phone))

    with pytest.raises(IntegrityError):
        await repo.create(_new_user(phone=phone))


@pytest.mark.asyncio
async def test_multiple_users_with_null_phone_allowed(db_session) -> None:
    repo = UserRepository(db_session)
    await repo.create(_new_user(phone=None))
    # Would raise IntegrityError above if PostgreSQL didn't treat every
    # NULL as distinct under a standard UNIQUE constraint.
    await repo.create(_new_user(phone=None))


@pytest.mark.asyncio
async def test_stored_password_hash_is_not_the_raw_password(db_session) -> None:
    raw_password = "correct horse battery staple"
    hashed = hash_password(raw_password)

    user = await UserRepository(db_session).create(_new_user(password_hash=hashed))

    assert user.password_hash != raw_password
    assert verify_password(raw_password, user.password_hash)


@pytest.mark.asyncio
async def test_rollback_after_failure_leaves_no_partial_record(db_session) -> None:
    email = f"rollback-{uuid.uuid4()}@example.com"
    repo = UserRepository(db_session)

    try:
        await repo.create(_new_user(email=email))
        raise RuntimeError("simulated failure before commit")
    except RuntimeError:
        await db_session.rollback()

    assert await repo.get_by_email(email) is None
