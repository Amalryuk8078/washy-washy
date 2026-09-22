"""Integration tests for CustomerProfile/PartnerProfile against a real
PostgreSQL database. See tests/integration/conftest.py's db_session
fixture.
"""

import uuid

import pytest

from core.exceptions import ConflictException, NotFoundException
from washy_washy.services.auth_service import AuthService
from washy_washy.services.profile_service import ProfileService


async def _make_user(db_session):
    return await AuthService(db_session).register(
        email=f"user-{uuid.uuid4()}@example.com", password="longenough1", first_name="Test"
    )


@pytest.mark.asyncio
async def test_create_and_get_customer_profile(db_session) -> None:
    user = await _make_user(db_session)
    service = ProfileService(db_session)

    created = await service.create_customer_profile(user.id, display_name="Ami")
    fetched = await service.get_customer_profile(user.id)

    assert fetched.id == created.id
    assert fetched.display_name == "Ami"


@pytest.mark.asyncio
async def test_duplicate_customer_profile_rejected(db_session) -> None:
    user = await _make_user(db_session)
    service = ProfileService(db_session)
    await service.create_customer_profile(user.id)

    with pytest.raises(ConflictException):
        await service.create_customer_profile(user.id)


@pytest.mark.asyncio
async def test_get_customer_profile_not_found(db_session) -> None:
    user = await _make_user(db_session)

    with pytest.raises(NotFoundException):
        await ProfileService(db_session).get_customer_profile(user.id)


@pytest.mark.asyncio
async def test_create_and_get_partner_profile(db_session) -> None:
    user = await _make_user(db_session)
    service = ProfileService(db_session)

    created = await service.create_partner_profile(
        user.id, business_name="Sparkle Laundry", contact_phone="+15551234567"
    )
    fetched = await service.get_partner_profile(user.id)

    assert fetched.id == created.id
    assert fetched.business_name == "Sparkle Laundry"
    assert fetched.status == "PENDING"


@pytest.mark.asyncio
async def test_duplicate_partner_profile_rejected(db_session) -> None:
    user = await _make_user(db_session)
    service = ProfileService(db_session)
    await service.create_partner_profile(user.id, business_name="Sparkle Laundry")

    with pytest.raises(ConflictException):
        await service.create_partner_profile(user.id, business_name="Another Name")


@pytest.mark.asyncio
async def test_customer_and_partner_profiles_are_independent(db_session) -> None:
    # Same user can hold both -- a profile isn't a role, and doesn't
    # exclude the other.
    user = await _make_user(db_session)
    service = ProfileService(db_session)

    await service.create_customer_profile(user.id, display_name="Ami")
    await service.create_partner_profile(user.id, business_name="Sparkle Laundry")

    assert (await service.get_customer_profile(user.id)).display_name == "Ami"
    assert (await service.get_partner_profile(user.id)).business_name == "Sparkle Laundry"
