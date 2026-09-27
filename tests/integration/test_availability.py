"""Integration tests for AvailabilityService — operating hours, partner
availability, slot creation, and booking/cancellation — against a real
PostgreSQL database. Real *concurrent* overbooking prevention is
covered separately in test_availability_concurrency.py; this file
covers the sequential logic and business rules.
"""

import uuid
from datetime import date, time
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.operating_hours import DayOfWeek
from washy_washy.services.auth_service import AuthService
from washy_washy.services.availability_service import AvailabilityService
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.partner_capability_service import PartnerCapabilityService
from washy_washy.services.profile_service import ProfileService
from washy_washy.services.service_area_service import ServiceAreaService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


async def _make_service_area(db_session):
    return await ServiceAreaService(db_session).create_service_area(_unique("Area"), [])


async def _make_customer(db_session):
    return await AuthService(db_session).register(
        email=f"{_unique('customer')}@example.com", password="longenough1", first_name="Cust"
    )


async def _make_partner_profile(db_session):
    user = await AuthService(db_session).register(
        email=f"{_unique('partner')}@example.com", password="longenough1", first_name="Partner"
    )
    return await ProfileService(db_session).create_partner_profile(
        user.id, business_name=_unique("Laundry")
    )


@pytest.mark.asyncio
async def test_set_and_get_operating_hours(db_session) -> None:
    area = await _make_service_area(db_session)
    service = AvailabilityService(db_session)

    hours = await service.set_operating_hours(
        area.id, DayOfWeek.MONDAY.value, time(9, 0), time(18, 0)
    )

    assert hours.is_active is True
    all_hours = await service.get_operating_hours(area.id)
    assert [h.id for h in all_hours] == [hours.id]


@pytest.mark.asyncio
async def test_setting_operating_hours_twice_updates_in_place(db_session) -> None:
    area = await _make_service_area(db_session)
    service = AvailabilityService(db_session)
    first = await service.set_operating_hours(
        area.id, DayOfWeek.MONDAY.value, time(9, 0), time(18, 0)
    )

    second = await service.set_operating_hours(
        area.id, DayOfWeek.MONDAY.value, time(10, 0), time(17, 0)
    )

    assert first.id == second.id
    assert second.opening_time == time(10, 0)


@pytest.mark.asyncio
async def test_is_open_true_within_hours_false_outside(db_session) -> None:
    area = await _make_service_area(db_session)
    service = AvailabilityService(db_session)
    await service.set_operating_hours(area.id, DayOfWeek.MONDAY.value, time(9, 0), time(18, 0))

    assert await service.is_open(area.id, DayOfWeek.MONDAY.value, time(12, 0)) is True
    assert await service.is_open(area.id, DayOfWeek.MONDAY.value, time(8, 0)) is False
    assert await service.is_open(area.id, DayOfWeek.MONDAY.value, time(19, 0)) is False


@pytest.mark.asyncio
async def test_is_open_false_for_a_day_with_no_hours_defined(db_session) -> None:
    area = await _make_service_area(db_session)
    service = AvailabilityService(db_session)

    assert await service.is_open(area.id, DayOfWeek.SUNDAY.value, time(12, 0)) is False


@pytest.mark.asyncio
async def test_closed_day_overrides_previously_set_hours(db_session) -> None:
    area = await _make_service_area(db_session)
    service = AvailabilityService(db_session)
    await service.set_operating_hours(area.id, DayOfWeek.SUNDAY.value, time(9, 0), time(18, 0))
    assert await service.is_open(area.id, DayOfWeek.SUNDAY.value, time(12, 0)) is True

    await service.close_day(area.id, DayOfWeek.SUNDAY.value)

    assert await service.is_open(area.id, DayOfWeek.SUNDAY.value, time(12, 0)) is False


@pytest.mark.asyncio
async def test_partner_availability_round_trip(db_session) -> None:
    partner_profile = await _make_partner_profile(db_session)
    service = AvailabilityService(db_session)

    await service.set_partner_availability(
        partner_profile.id, DayOfWeek.TUESDAY.value, time(8, 0), time(16, 0)
    )

    assert (
        await service.is_partner_available(partner_profile.id, DayOfWeek.TUESDAY.value, time(9, 0))
        is True
    )
    assert (
        await service.is_partner_available(partner_profile.id, DayOfWeek.TUESDAY.value, time(17, 0))
        is False
    )
    assert (
        await service.is_partner_available(
            partner_profile.id, DayOfWeek.WEDNESDAY.value, time(9, 0)
        )
        is False
    )


@pytest.mark.asyncio
async def test_has_capable_partner(db_session) -> None:
    service_obj = await CatalogService(db_session).create_service(_unique("Wash"))
    partner_profile = await _make_partner_profile(db_session)
    availability = AvailabilityService(db_session)

    assert await availability.has_capable_partner(service_obj.id) is False

    await PartnerCapabilityService(db_session).grant_capability(partner_profile.id, service_obj.id)

    assert await availability.has_capable_partner(service_obj.id) is True


@pytest.mark.asyncio
async def test_create_and_list_pickup_slots(db_session) -> None:
    area = await _make_service_area(db_session)
    service = AvailabilityService(db_session)

    slot = await service.create_pickup_slot(
        area.id, date.today(), time(9, 0), time(11, 0), "ORDERS", Decimal("5")
    )

    slots = await service.list_pickup_slots(area.id)
    assert [s.id for s in slots] == [slot.id]
    assert slot.capacity_reserved == Decimal("0")


@pytest.mark.asyncio
async def test_pickup_and_delivery_slots_are_independent(db_session) -> None:
    area = await _make_service_area(db_session)
    service = AvailabilityService(db_session)
    await service.create_pickup_slot(
        area.id, date.today(), time(9, 0), time(11, 0), "ORDERS", Decimal("5")
    )
    await service.create_delivery_slot(
        area.id, date.today(), time(14, 0), time(16, 0), "ORDERS", Decimal("5")
    )

    pickup_slots = await service.list_pickup_slots(area.id)
    delivery_slots = await service.list_delivery_slots(area.id)

    assert len(pickup_slots) == 1
    assert len(delivery_slots) == 1
    assert pickup_slots[0].id != delivery_slots[0].id


@pytest.mark.asyncio
async def test_book_pickup_slot_reserves_capacity(db_session) -> None:
    area = await _make_service_area(db_session)
    customer = await _make_customer(db_session)
    service = AvailabilityService(db_session)
    slot = await service.create_pickup_slot(
        area.id, date.today(), time(9, 0), time(11, 0), "ORDERS", Decimal("5")
    )

    reservation = await service.book_pickup_slot(slot.id, customer.id, Decimal("2"))

    assert reservation.capacity_used == Decimal("2")
    updated = (await service.list_pickup_slots(area.id))[0]
    assert updated.capacity_reserved == Decimal("2")


@pytest.mark.asyncio
async def test_book_pickup_slot_exceeding_capacity_rejected(db_session) -> None:
    area = await _make_service_area(db_session)
    customer = await _make_customer(db_session)
    service = AvailabilityService(db_session)
    slot = await service.create_pickup_slot(
        area.id, date.today(), time(9, 0), time(11, 0), "ORDERS", Decimal("2")
    )
    await service.book_pickup_slot(slot.id, customer.id, Decimal("2"))

    with pytest.raises(BusinessRuleException):
        await service.book_pickup_slot(slot.id, customer.id, Decimal("1"))


@pytest.mark.asyncio
async def test_book_nonexistent_pickup_slot_raises_not_found(db_session) -> None:
    customer = await _make_customer(db_session)

    with pytest.raises(NotFoundException):
        await AvailabilityService(db_session).book_pickup_slot(
            uuid.uuid4(), customer.id, Decimal("1")
        )


@pytest.mark.asyncio
async def test_cancel_pickup_reservation_releases_capacity(db_session) -> None:
    area = await _make_service_area(db_session)
    customer = await _make_customer(db_session)
    service = AvailabilityService(db_session)
    slot = await service.create_pickup_slot(
        area.id, date.today(), time(9, 0), time(11, 0), "ORDERS", Decimal("5")
    )
    reservation = await service.book_pickup_slot(slot.id, customer.id, Decimal("3"))

    await service.cancel_pickup_reservation(reservation.id, customer.id)

    updated = (await service.list_pickup_slots(area.id))[0]
    assert updated.capacity_reserved == Decimal("0")


@pytest.mark.asyncio
async def test_cancel_pickup_reservation_by_non_owner_raises_not_found(db_session) -> None:
    area = await _make_service_area(db_session)
    owner = await _make_customer(db_session)
    intruder = await _make_customer(db_session)
    service = AvailabilityService(db_session)
    slot = await service.create_pickup_slot(
        area.id, date.today(), time(9, 0), time(11, 0), "ORDERS", Decimal("5")
    )
    reservation = await service.book_pickup_slot(slot.id, owner.id, Decimal("1"))

    with pytest.raises(NotFoundException):
        await service.cancel_pickup_reservation(reservation.id, intruder.id)


@pytest.mark.asyncio
async def test_cancelling_twice_is_idempotent(db_session) -> None:
    area = await _make_service_area(db_session)
    customer = await _make_customer(db_session)
    service = AvailabilityService(db_session)
    slot = await service.create_pickup_slot(
        area.id, date.today(), time(9, 0), time(11, 0), "ORDERS", Decimal("5")
    )
    reservation = await service.book_pickup_slot(slot.id, customer.id, Decimal("2"))
    await service.cancel_pickup_reservation(reservation.id, customer.id)

    # Second cancel must not release capacity again (would go negative
    # or double-free it).
    await service.cancel_pickup_reservation(reservation.id, customer.id)

    updated = (await service.list_pickup_slots(area.id))[0]
    assert updated.capacity_reserved == Decimal("0")


@pytest.mark.asyncio
async def test_book_and_cancel_delivery_slot(db_session) -> None:
    area = await _make_service_area(db_session)
    customer = await _make_customer(db_session)
    service = AvailabilityService(db_session)
    slot = await service.create_delivery_slot(
        area.id, date.today(), time(14, 0), time(16, 0), "WEIGHT_KG", Decimal("10.5")
    )

    reservation = await service.book_delivery_slot(slot.id, customer.id, Decimal("4.5"))
    updated = (await service.list_delivery_slots(area.id))[0]
    assert updated.capacity_reserved == Decimal("4.5")

    await service.cancel_delivery_reservation(reservation.id, customer.id)
    updated = (await service.list_delivery_slots(area.id))[0]
    assert updated.capacity_reserved == Decimal("0")
