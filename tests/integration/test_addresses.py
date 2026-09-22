"""Integration tests for Address ownership, CRUD, and the transaction-safe
"set as default" operation, against a real PostgreSQL database.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from core.exceptions import NotFoundException
from core.models.address import Address
from washy_washy.schemas.address import AddressResponse
from washy_washy.services.address_service import AddressService
from washy_washy.services.auth_service import AuthService


async def _make_user(db_session):
    return await AuthService(db_session).register(
        email=f"user-{uuid.uuid4()}@example.com", password="longenough1", first_name="Test"
    )


def _address_kwargs(**overrides):
    defaults = {
        "address_line_1": "221B Baker Street",
        "city": "London",
        "state": "London",
        "postal_code": "NW16XE",
        "country": "UK",
        "label": "HOME",
    }
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_create_address(db_session) -> None:
    user = await _make_user(db_session)
    service = AddressService(db_session)

    address = await service.create_address(user.id, **_address_kwargs())

    assert isinstance(address.id, uuid.UUID)
    assert address.user_id == user.id
    assert address.is_default is False


@pytest.mark.asyncio
async def test_list_addresses_returns_only_own(db_session) -> None:
    owner = await _make_user(db_session)
    other = await _make_user(db_session)
    service = AddressService(db_session)
    await service.create_address(owner.id, **_address_kwargs())
    await service.create_address(other.id, **_address_kwargs())

    addresses = await service.list_addresses(owner.id)

    assert len(addresses) == 1
    assert addresses[0].user_id == owner.id


@pytest.mark.asyncio
async def test_cross_user_address_access_raises_not_found(db_session) -> None:
    owner = await _make_user(db_session)
    intruder = await _make_user(db_session)
    service = AddressService(db_session)
    address = await service.create_address(owner.id, **_address_kwargs())

    with pytest.raises(NotFoundException):
        await service.get_own_address(intruder.id, address.id)


@pytest.mark.asyncio
async def test_update_address_changes_only_given_fields(db_session) -> None:
    user = await _make_user(db_session)
    service = AddressService(db_session)
    address = await service.create_address(user.id, **_address_kwargs(city="London"))

    updated = await service.update_address(user.id, address.id, city="Manchester")

    assert updated.city == "Manchester"
    assert updated.address_line_1 == "221B Baker Street"


@pytest.mark.asyncio
async def test_update_address_rejects_non_owner(db_session) -> None:
    owner = await _make_user(db_session)
    intruder = await _make_user(db_session)
    service = AddressService(db_session)
    address = await service.create_address(owner.id, **_address_kwargs())

    with pytest.raises(NotFoundException):
        await service.update_address(intruder.id, address.id, city="Nowhere")


@pytest.mark.asyncio
async def test_delete_address(db_session) -> None:
    user = await _make_user(db_session)
    service = AddressService(db_session)
    address = await service.create_address(user.id, **_address_kwargs())

    await service.delete_address(user.id, address.id)

    assert await service.list_addresses(user.id) == []


@pytest.mark.asyncio
async def test_delete_address_rejects_non_owner(db_session) -> None:
    owner = await _make_user(db_session)
    intruder = await _make_user(db_session)
    service = AddressService(db_session)
    address = await service.create_address(owner.id, **_address_kwargs())

    with pytest.raises(NotFoundException):
        await service.delete_address(intruder.id, address.id)


@pytest.mark.asyncio
async def test_set_default_address_flips_previous_default(db_session) -> None:
    user = await _make_user(db_session)
    service = AddressService(db_session)
    first = await service.create_address(user.id, **_address_kwargs(is_default=True))
    second = await service.create_address(user.id, **_address_kwargs(city="Manchester"))

    result = await service.set_default_address(user.id, second.id)

    assert result.is_default is True
    refreshed_first = await service.get_own_address(user.id, first.id)
    assert refreshed_first.is_default is False


@pytest.mark.asyncio
async def test_create_address_with_is_default_true(db_session) -> None:
    user = await _make_user(db_session)
    service = AddressService(db_session)

    address = await service.create_address(user.id, **_address_kwargs(is_default=True))

    assert address.is_default is True


@pytest.mark.asyncio
async def test_create_default_address_response_serializes_without_error(db_session) -> None:
    # Regression test: creating with is_default=True triggers a second
    # flush (the default-flip UPDATE) after the initial INSERT. Without
    # eager_defaults on the model (see core/models/mixins.py), the
    # UPDATE-refreshed updated_at came back "expired," and reading it
    # here -- via a synchronous Pydantic model_validate, exactly what the
    # real controller does -- raised MissingGreenlet instead of a clean
    # 500 test failure. A plain `address.is_default is True` assertion
    # (as in the test above) doesn't touch updated_at and would never
    # have caught this.
    user = await _make_user(db_session)
    service = AddressService(db_session)

    address = await service.create_address(user.id, **_address_kwargs(is_default=True))
    response = AddressResponse.model_validate(address)

    assert response.is_default is True
    assert response.updated_at is not None


@pytest.mark.asyncio
async def test_database_rejects_two_default_addresses_for_same_user(db_session) -> None:
    # Bypasses AddressService entirely -- proves the partial unique index
    # itself is the real guard, not just application logic.
    user = await _make_user(db_session)
    db_session.add(Address(user_id=user.id, is_default=True, **_address_kwargs()))
    await db_session.flush()

    db_session.add(Address(user_id=user.id, is_default=True, **_address_kwargs(city="Manchester")))
    with pytest.raises(IntegrityError):
        await db_session.flush()
