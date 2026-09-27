"""Integration tests for CatalogService (services, materials, and their
compatibility) and PartnerCapabilityService, against a real PostgreSQL
database.
"""

import uuid

import pytest

from core.exceptions import ConflictException, NotFoundException
from washy_washy.services.auth_service import AuthService
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.partner_capability_service import PartnerCapabilityService
from washy_washy.services.profile_service import ProfileService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


@pytest.mark.asyncio
async def test_create_service(db_session) -> None:
    service = await CatalogService(db_session).create_service(_unique("Wash"))

    assert isinstance(service.id, uuid.UUID)
    assert service.is_active is True


@pytest.mark.asyncio
async def test_duplicate_service_name_rejected(db_session) -> None:
    catalog = CatalogService(db_session)
    name = _unique("Wash")
    await catalog.create_service(name)

    with pytest.raises(ConflictException):
        await catalog.create_service(name)


@pytest.mark.asyncio
async def test_service_not_found(db_session) -> None:
    with pytest.raises(NotFoundException):
        await CatalogService(db_session).get_service(uuid.uuid4())


@pytest.mark.asyncio
async def test_service_activation_and_deactivation(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Iron"))

    deactivated = await catalog.set_service_active(service.id, False)
    assert deactivated.is_active is False

    reactivated = await catalog.set_service_active(service.id, True)
    assert reactivated.is_active is True


@pytest.mark.asyncio
async def test_list_services_excludes_inactive_by_default(db_session) -> None:
    catalog = CatalogService(db_session)
    active = await catalog.create_service(_unique("Active"))
    inactive = await catalog.create_service(_unique("Inactive"))
    await catalog.set_service_active(inactive.id, False)

    visible_ids = {s.id for s in await catalog.list_services()}
    assert active.id in visible_ids
    assert inactive.id not in visible_ids

    all_ids = {s.id for s in await catalog.list_services(include_inactive=True)}
    assert inactive.id in all_ids


@pytest.mark.asyncio
async def test_create_material_and_duplicate_rejected(db_session) -> None:
    catalog = CatalogService(db_session)
    name = _unique("Cotton")
    material = await catalog.create_material(name)

    assert material.is_active is True
    with pytest.raises(ConflictException):
        await catalog.create_material(name)


@pytest.mark.asyncio
async def test_material_activation_and_deactivation(db_session) -> None:
    catalog = CatalogService(db_session)
    material = await catalog.create_material(_unique("Wool"))

    deactivated = await catalog.set_material_active(material.id, False)
    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_set_and_query_compatibility(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    material = await catalog.create_material(_unique("Cotton"))

    await catalog.set_compatibility(
        service.id, material.id, care_instructions="Machine wash cold", max_temperature_celsius=30
    )

    assert await catalog.is_compatible(service.id, material.id) is True
    materials = await catalog.get_compatible_materials(service.id)
    assert [m.id for m in materials] == [material.id]
    services = await catalog.get_compatible_services(material.id)
    assert [s.id for s in services] == [service.id]


@pytest.mark.asyncio
async def test_incompatible_pair_is_not_compatible(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Dry Clean"))
    material = await catalog.create_material(_unique("Denim"))

    assert await catalog.is_compatible(service.id, material.id) is False
    assert await catalog.get_compatible_materials(service.id) == []


@pytest.mark.asyncio
async def test_set_compatibility_twice_updates_in_place_not_duplicated(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    material = await catalog.create_material(_unique("Silk"))

    first = await catalog.set_compatibility(service.id, material.id, max_temperature_celsius=40)
    second = await catalog.set_compatibility(service.id, material.id, max_temperature_celsius=20)

    assert first.id == second.id
    assert second.max_temperature_celsius == 20
    assert len(await catalog.get_compatible_materials(service.id)) == 1


@pytest.mark.asyncio
async def test_set_compatibility_for_nonexistent_service_raises_not_found(db_session) -> None:
    catalog = CatalogService(db_session)
    material = await catalog.create_material(_unique("Leather"))

    with pytest.raises(NotFoundException):
        await catalog.set_compatibility(uuid.uuid4(), material.id)


@pytest.mark.asyncio
async def test_set_compatibility_for_nonexistent_material_raises_not_found(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))

    with pytest.raises(NotFoundException):
        await catalog.set_compatibility(service.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_remove_compatibility(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    material = await catalog.create_material(_unique("Cotton"))
    await catalog.set_compatibility(service.id, material.id)

    await catalog.remove_compatibility(service.id, material.id)

    assert await catalog.is_compatible(service.id, material.id) is False


async def _make_partner_profile(db_session):
    user = await AuthService(db_session).register(
        email=f"{_unique('partner')}@example.com", password="longenough1", first_name="Partner"
    )
    return await ProfileService(db_session).create_partner_profile(
        user.id, business_name=_unique("Sparkle Laundry")
    )


@pytest.mark.asyncio
async def test_grant_and_check_partner_capability(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    partner_profile = await _make_partner_profile(db_session)
    capability_service = PartnerCapabilityService(db_session)

    await capability_service.grant_capability(partner_profile.id, service.id)

    assert await capability_service.has_capability(partner_profile.id, service.id) is True
    services = await capability_service.list_services_for_partner(partner_profile.id)
    assert [s.id for s in services] == [service.id]


@pytest.mark.asyncio
async def test_duplicate_partner_capability_rejected(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    partner_profile = await _make_partner_profile(db_session)
    capability_service = PartnerCapabilityService(db_session)
    await capability_service.grant_capability(partner_profile.id, service.id)

    with pytest.raises(ConflictException):
        await capability_service.grant_capability(partner_profile.id, service.id)


@pytest.mark.asyncio
async def test_revoke_partner_capability(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    partner_profile = await _make_partner_profile(db_session)
    capability_service = PartnerCapabilityService(db_session)
    await capability_service.grant_capability(partner_profile.id, service.id)

    await capability_service.revoke_capability(partner_profile.id, service.id)

    assert await capability_service.has_capability(partner_profile.id, service.id) is False


@pytest.mark.asyncio
async def test_grant_capability_for_nonexistent_partner_raises_not_found(db_session) -> None:
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))

    with pytest.raises(NotFoundException):
        await PartnerCapabilityService(db_session).grant_capability(uuid.uuid4(), service.id)


@pytest.mark.asyncio
async def test_grant_capability_for_nonexistent_service_raises_not_found(db_session) -> None:
    partner_profile = await _make_partner_profile(db_session)

    with pytest.raises(NotFoundException):
        await PartnerCapabilityService(db_session).grant_capability(
            partner_profile.id, uuid.uuid4()
        )
