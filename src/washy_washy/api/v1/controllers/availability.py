"""Request-level orchestration for the availability/slot/capacity
endpoints.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.availability import (
    BookSlotRequest,
    CreateSlotRequest,
    OperatingHoursResponse,
    PartnerAvailabilityResponse,
    SetOperatingHoursRequest,
    SetPartnerAvailabilityRequest,
    SlotReservationResponse,
    SlotResponse,
)
from washy_washy.services.availability_service import AvailabilityService


async def set_operating_hours(
    service_area_id: uuid.UUID, request: SetOperatingHoursRequest, db_session: AsyncSession
) -> OperatingHoursResponse:
    service = AvailabilityService(db_session)
    hours = await service.set_operating_hours(
        service_area_id, request.day_of_week, request.opening_time, request.closing_time
    )
    await db_session.commit()
    return OperatingHoursResponse.model_validate(hours)


async def get_operating_hours(
    service_area_id: uuid.UUID, db_session: AsyncSession
) -> list[OperatingHoursResponse]:
    service = AvailabilityService(db_session)
    hours = await service.get_operating_hours(service_area_id)
    return [OperatingHoursResponse.model_validate(h) for h in hours]


async def set_partner_availability(
    partner_profile_id: uuid.UUID,
    request: SetPartnerAvailabilityRequest,
    db_session: AsyncSession,
) -> PartnerAvailabilityResponse:
    service = AvailabilityService(db_session)
    availability = await service.set_partner_availability(
        partner_profile_id, request.day_of_week, request.start_time, request.end_time
    )
    await db_session.commit()
    return PartnerAvailabilityResponse.model_validate(availability)


async def get_partner_availability(
    partner_profile_id: uuid.UUID, db_session: AsyncSession
) -> list[PartnerAvailabilityResponse]:
    service = AvailabilityService(db_session)
    availability = await service.get_partner_availability(partner_profile_id)
    return [PartnerAvailabilityResponse.model_validate(a) for a in availability]


async def create_pickup_slot(
    service_area_id: uuid.UUID, request: CreateSlotRequest, db_session: AsyncSession
) -> SlotResponse:
    service = AvailabilityService(db_session)
    slot = await service.create_pickup_slot(
        service_area_id,
        request.slot_date,
        request.start_time,
        request.end_time,
        request.capacity_unit,
        request.capacity_total,
    )
    await db_session.commit()
    return SlotResponse.model_validate(slot)


async def list_pickup_slots(
    service_area_id: uuid.UUID, db_session: AsyncSession
) -> list[SlotResponse]:
    service = AvailabilityService(db_session)
    slots = await service.list_pickup_slots(service_area_id)
    return [SlotResponse.model_validate(s) for s in slots]


async def create_delivery_slot(
    service_area_id: uuid.UUID, request: CreateSlotRequest, db_session: AsyncSession
) -> SlotResponse:
    service = AvailabilityService(db_session)
    slot = await service.create_delivery_slot(
        service_area_id,
        request.slot_date,
        request.start_time,
        request.end_time,
        request.capacity_unit,
        request.capacity_total,
    )
    await db_session.commit()
    return SlotResponse.model_validate(slot)


async def list_delivery_slots(
    service_area_id: uuid.UUID, db_session: AsyncSession
) -> list[SlotResponse]:
    service = AvailabilityService(db_session)
    slots = await service.list_delivery_slots(service_area_id)
    return [SlotResponse.model_validate(s) for s in slots]


async def book_pickup_slot(
    slot_id: uuid.UUID,
    customer_user_id: uuid.UUID,
    request: BookSlotRequest,
    db_session: AsyncSession,
) -> SlotReservationResponse:
    service = AvailabilityService(db_session)
    reservation = await service.book_pickup_slot(slot_id, customer_user_id, request.capacity_used)
    await db_session.commit()
    return SlotReservationResponse.model_validate(reservation)


async def cancel_pickup_reservation(
    reservation_id: uuid.UUID, customer_user_id: uuid.UUID, db_session: AsyncSession
) -> None:
    service = AvailabilityService(db_session)
    await service.cancel_pickup_reservation(reservation_id, customer_user_id)
    await db_session.commit()


async def book_delivery_slot(
    slot_id: uuid.UUID,
    customer_user_id: uuid.UUID,
    request: BookSlotRequest,
    db_session: AsyncSession,
) -> SlotReservationResponse:
    service = AvailabilityService(db_session)
    reservation = await service.book_delivery_slot(slot_id, customer_user_id, request.capacity_used)
    await db_session.commit()
    return SlotReservationResponse.model_validate(reservation)


async def cancel_delivery_reservation(
    reservation_id: uuid.UUID, customer_user_id: uuid.UUID, db_session: AsyncSession
) -> None:
    service = AvailabilityService(db_session)
    await service.cancel_delivery_reservation(reservation_id, customer_user_id)
    await db_session.commit()
