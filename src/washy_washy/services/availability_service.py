"""Availability business logic: operating hours, partner availability,
pickup/delivery slots, and the concurrency-safe booking flow.

PostgreSQL is authoritative throughout — no Redis. Every capacity
change goes through the slot repositories' single atomic conditional
``UPDATE`` (see ``PickupSlotRepository.try_reserve_capacity``), which is
what actually makes concurrent bookings safe; nothing here reads
capacity then writes it back.

**Known scope gap, documented rather than papered over**: "availability
must consider [partner] capability" (the Phase 7 spec) ideally means a
booking checks that some partner *in that slot's service area* both has
`PartnerCapability` for the requested service and is available. That
requires a `PartnerProfile <-> ServiceArea` association that doesn't
exist yet (`PartnerProfile` has no service-area field) — building one
now, just to satisfy this, would be speculative ahead of Phase 9
("Partner Operations"), which is the natural place for that link.
`has_capable_partner` below answers the weaker, still-useful question
"does *any* partner support this service at all" and is available for
a caller to use, but slot booking does not hard-block on it.
"""

import uuid
from datetime import time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.delivery_slot import DeliverySlot
from core.models.delivery_slot_reservation import DeliverySlotReservation, ReservationStatus
from core.models.operating_hours import OperatingHours
from core.models.partner_availability import PartnerAvailability
from core.models.pickup_slot import PickupSlot
from core.models.pickup_slot_reservation import PickupSlotReservation
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.delivery_slot_repo import DeliverySlotRepository
from washy_washy.repositories.delivery_slot_reservation_repo import (
    DeliverySlotReservationRepository,
)
from washy_washy.repositories.operating_hours_repo import OperatingHoursRepository
from washy_washy.repositories.partner_availability_repo import PartnerAvailabilityRepository
from washy_washy.repositories.partner_capability_repo import PartnerCapabilityRepository
from washy_washy.repositories.pickup_slot_repo import PickupSlotRepository
from washy_washy.repositories.pickup_slot_reservation_repo import PickupSlotReservationRepository
from washy_washy.repositories.service_area_repo import ServiceAreaRepository


class AvailabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self._operating_hours = OperatingHoursRepository(session)
        self._partner_availability = PartnerAvailabilityRepository(session)
        self._pickup_slots = PickupSlotRepository(session)
        self._delivery_slots = DeliverySlotRepository(session)
        self._pickup_reservations = PickupSlotReservationRepository(session)
        self._delivery_reservations = DeliverySlotReservationRepository(session)
        self._partner_capabilities = PartnerCapabilityRepository(session)
        self._service_areas = ServiceAreaRepository(session)

    # -- Operating hours ---------------------------------------------------

    async def set_operating_hours(
        self, service_area_id: uuid.UUID, day_of_week: str, opening_time: time, closing_time: time
    ) -> OperatingHours:
        if await self._service_areas.get_by_id(service_area_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

        existing = await self._operating_hours.get(service_area_id, day_of_week)
        if existing is not None:
            existing.opening_time = opening_time
            existing.closing_time = closing_time
            existing.is_active = True
            return await self._operating_hours.update(existing)

        hours = OperatingHours(
            service_area_id=service_area_id,
            day_of_week=day_of_week,
            opening_time=opening_time,
            closing_time=closing_time,
        )
        return await self._operating_hours.create(hours)

    async def close_day(self, service_area_id: uuid.UUID, day_of_week: str) -> None:
        existing = await self._operating_hours.get(service_area_id, day_of_week)
        if existing is not None:
            existing.is_active = False
            await self._operating_hours.update(existing)

    async def get_operating_hours(self, service_area_id: uuid.UUID) -> list[OperatingHours]:
        return await self._operating_hours.list_for_service_area(service_area_id)

    async def is_open(self, service_area_id: uuid.UUID, day_of_week: str, at: time) -> bool:
        hours = await self._operating_hours.get(service_area_id, day_of_week)
        if hours is None or not hours.is_active:
            return False
        return hours.opening_time <= at < hours.closing_time

    # -- Partner availability ----------------------------------------------

    async def set_partner_availability(
        self, partner_profile_id: uuid.UUID, day_of_week: str, start_time: time, end_time: time
    ) -> PartnerAvailability:
        existing = await self._partner_availability.get(partner_profile_id, day_of_week)
        if existing is not None:
            existing.start_time = start_time
            existing.end_time = end_time
            existing.is_active = True
            return await self._partner_availability.update(existing)

        availability = PartnerAvailability(
            partner_profile_id=partner_profile_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
        )
        return await self._partner_availability.create(availability)

    async def get_partner_availability(
        self, partner_profile_id: uuid.UUID
    ) -> list[PartnerAvailability]:
        return await self._partner_availability.list_for_partner(partner_profile_id)

    async def is_partner_available(
        self, partner_profile_id: uuid.UUID, day_of_week: str, at: time
    ) -> bool:
        availability = await self._partner_availability.get(partner_profile_id, day_of_week)
        if availability is None or not availability.is_active:
            return False
        return availability.start_time <= at < availability.end_time

    async def has_capable_partner(self, service_id: uuid.UUID) -> bool:
        """Weaker than a true area-aware capability check — see the
        module docstring for why.
        """
        return await self._partner_capabilities.has_any_capability_for_service(service_id)

    # -- Slots ---------------------------------------------------------------

    async def create_pickup_slot(
        self,
        service_area_id: uuid.UUID,
        slot_date,
        start_time: time,
        end_time: time,
        capacity_unit: str,
        capacity_total: Decimal,
    ) -> PickupSlot:
        if await self._service_areas.get_by_id(service_area_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        slot = PickupSlot(
            service_area_id=service_area_id,
            slot_date=slot_date,
            start_time=start_time,
            end_time=end_time,
            capacity_unit=capacity_unit,
            capacity_total=capacity_total,
        )
        return await self._pickup_slots.create(slot)

    async def create_delivery_slot(
        self,
        service_area_id: uuid.UUID,
        slot_date,
        start_time: time,
        end_time: time,
        capacity_unit: str,
        capacity_total: Decimal,
    ) -> DeliverySlot:
        if await self._service_areas.get_by_id(service_area_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        slot = DeliverySlot(
            service_area_id=service_area_id,
            slot_date=slot_date,
            start_time=start_time,
            end_time=end_time,
            capacity_unit=capacity_unit,
            capacity_total=capacity_total,
        )
        return await self._delivery_slots.create(slot)

    async def list_pickup_slots(self, service_area_id: uuid.UUID) -> list[PickupSlot]:
        return await self._pickup_slots.list_for_service_area(service_area_id)

    async def list_delivery_slots(self, service_area_id: uuid.UUID) -> list[DeliverySlot]:
        return await self._delivery_slots.list_for_service_area(service_area_id)

    # -- Booking -------------------------------------------------------------

    async def book_pickup_slot(
        self, slot_id: uuid.UUID, customer_user_id: uuid.UUID, capacity_used: Decimal
    ) -> PickupSlotReservation:
        if await self._pickup_slots.get_by_id(slot_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

        reserved = await self._pickup_slots.try_reserve_capacity(slot_id, capacity_used)
        if not reserved:
            raise BusinessRuleException(
                error_messages.SLOT_CAPACITY_EXCEEDED, error_codes.SLOT_CAPACITY_EXCEEDED
            )

        reservation = PickupSlotReservation(
            slot_id=slot_id, customer_user_id=customer_user_id, capacity_used=capacity_used
        )
        return await self._pickup_reservations.create(reservation)

    async def cancel_pickup_reservation(
        self, reservation_id: uuid.UUID, customer_user_id: uuid.UUID
    ) -> None:
        """``customer_user_id`` must match the reservation's own owner —
        same security posture as ``AddressService.get_own_address``: a
        caller who doesn't own the reservation gets a plain 404, never
        confirmation that a different customer's reservation exists.
        """
        reservation = await self._pickup_reservations.get_by_id(reservation_id)
        if reservation is None or reservation.customer_user_id != customer_user_id:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if reservation.status != ReservationStatus.ACTIVE:
            return  # Idempotent: cancelling an already-cancelled reservation is a no-op.

        reservation.status = ReservationStatus.CANCELLED
        await self._pickup_reservations.update(reservation)
        await self._pickup_slots.release_capacity(reservation.slot_id, reservation.capacity_used)

    async def book_delivery_slot(
        self, slot_id: uuid.UUID, customer_user_id: uuid.UUID, capacity_used: Decimal
    ) -> DeliverySlotReservation:
        if await self._delivery_slots.get_by_id(slot_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

        reserved = await self._delivery_slots.try_reserve_capacity(slot_id, capacity_used)
        if not reserved:
            raise BusinessRuleException(
                error_messages.SLOT_CAPACITY_EXCEEDED, error_codes.SLOT_CAPACITY_EXCEEDED
            )

        reservation = DeliverySlotReservation(
            slot_id=slot_id, customer_user_id=customer_user_id, capacity_used=capacity_used
        )
        return await self._delivery_reservations.create(reservation)

    async def cancel_delivery_reservation(
        self, reservation_id: uuid.UUID, customer_user_id: uuid.UUID
    ) -> None:
        reservation = await self._delivery_reservations.get_by_id(reservation_id)
        if reservation is None or reservation.customer_user_id != customer_user_id:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if reservation.status != ReservationStatus.ACTIVE:
            return

        reservation.status = ReservationStatus.CANCELLED
        await self._delivery_reservations.update(reservation)
        await self._delivery_slots.release_capacity(reservation.slot_id, reservation.capacity_used)
