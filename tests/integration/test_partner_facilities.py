"""Integration tests for PartnerFacilityService and the partner-status
lifecycle (ProfileService.update_partner_status) — against a real
PostgreSQL database.
"""

import uuid

import pytest

from core.exceptions import ConflictException, NotFoundException
from core.models.partner_profile import PartnerStatus
from washy_washy.services.auth_service import AuthService
from washy_washy.services.facility_service import PartnerFacilityService
from washy_washy.services.profile_service import ProfileService
from washy_washy.services.service_area_service import ServiceAreaService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


async def _make_partner_profile(db_session):
    user = await AuthService(db_session).register(
        email=f"{_unique('partner')}@example.com", password="longenough1", first_name="Partner"
    )
    return await ProfileService(db_session).create_partner_profile(
        user.id, business_name=_unique("Laundry")
    )


async def _make_service_area(db_session):
    return await ServiceAreaService(db_session).create_service_area(_unique("Area"), [])


@pytest.mark.asyncio
async def test_create_facility_success(db_session) -> None:
    partner = await _make_partner_profile(db_session)
    area = await _make_service_area(db_session)

    facility = await PartnerFacilityService(db_session).create_facility(
        partner.id,
        area.id,
        name="Downtown Site",
        address_line_1="1 Wash St",
        city="Metropolis",
        state="State",
        postal_code="12345",
        country="Country",
    )

    assert facility.partner_profile_id == partner.id
    assert facility.service_area_id == area.id
    assert facility.is_active is True


@pytest.mark.asyncio
async def test_create_facility_duplicate_name_for_same_partner_rejected(db_session) -> None:
    partner = await _make_partner_profile(db_session)
    area = await _make_service_area(db_session)
    service = PartnerFacilityService(db_session)
    await service.create_facility(
        partner.id,
        area.id,
        name="Same Name",
        address_line_1="1 Wash St",
        city="Metropolis",
        state="State",
        postal_code="12345",
        country="Country",
    )

    with pytest.raises(ConflictException):
        await service.create_facility(
            partner.id,
            area.id,
            name="Same Name",
            address_line_1="2 Wash St",
            city="Metropolis",
            state="State",
            postal_code="12345",
            country="Country",
        )


@pytest.mark.asyncio
async def test_create_facility_nonexistent_partner_raises_not_found(db_session) -> None:
    area = await _make_service_area(db_session)

    with pytest.raises(NotFoundException):
        await PartnerFacilityService(db_session).create_facility(
            uuid.uuid4(),
            area.id,
            name="Nowhere",
            address_line_1="1 Wash St",
            city="Metropolis",
            state="State",
            postal_code="12345",
            country="Country",
        )


@pytest.mark.asyncio
async def test_create_facility_nonexistent_service_area_raises_not_found(db_session) -> None:
    partner = await _make_partner_profile(db_session)

    with pytest.raises(NotFoundException):
        await PartnerFacilityService(db_session).create_facility(
            partner.id,
            uuid.uuid4(),
            name="Nowhere",
            address_line_1="1 Wash St",
            city="Metropolis",
            state="State",
            postal_code="12345",
            country="Country",
        )


@pytest.mark.asyncio
async def test_list_facilities_for_partner_excludes_other_partners(db_session) -> None:
    partner_a = await _make_partner_profile(db_session)
    partner_b = await _make_partner_profile(db_session)
    area = await _make_service_area(db_session)
    service = PartnerFacilityService(db_session)
    await service.create_facility(
        partner_a.id,
        area.id,
        name="A Site",
        address_line_1="1 Wash St",
        city="Metropolis",
        state="State",
        postal_code="12345",
        country="Country",
    )
    await service.create_facility(
        partner_b.id,
        area.id,
        name="B Site",
        address_line_1="2 Wash St",
        city="Metropolis",
        state="State",
        postal_code="12345",
        country="Country",
    )

    facilities = await service.list_facilities_for_partner(partner_a.id)
    assert len(facilities) == 1
    assert facilities[0].partner_profile_id == partner_a.id


@pytest.mark.asyncio
async def test_set_active_toggles_and_is_excluded_from_default_listing(db_session) -> None:
    partner = await _make_partner_profile(db_session)
    area = await _make_service_area(db_session)
    service = PartnerFacilityService(db_session)
    facility = await service.create_facility(
        partner.id,
        area.id,
        name="Togglable",
        address_line_1="1 Wash St",
        city="Metropolis",
        state="State",
        postal_code="12345",
        country="Country",
    )

    await service.set_active(facility.id, False)

    active_only = await service.list_facilities_for_partner(partner.id)
    assert facility.id not in [f.id for f in active_only]
    including_inactive = await service.list_facilities_for_partner(
        partner.id, include_inactive=True
    )
    assert facility.id in [f.id for f in including_inactive]


@pytest.mark.asyncio
async def test_update_partner_status_lifecycle(db_session) -> None:
    partner = await _make_partner_profile(db_session)
    assert partner.status == PartnerStatus.PENDING.value

    updated = await ProfileService(db_session).update_partner_status(
        partner.id, PartnerStatus.ACTIVE.value
    )
    assert updated.status == PartnerStatus.ACTIVE.value

    suspended = await ProfileService(db_session).update_partner_status(
        partner.id, PartnerStatus.SUSPENDED.value
    )
    assert suspended.status == PartnerStatus.SUSPENDED.value


@pytest.mark.asyncio
async def test_update_partner_status_nonexistent_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundException):
        await ProfileService(db_session).update_partner_status(
            uuid.uuid4(), PartnerStatus.ACTIVE.value
        )
