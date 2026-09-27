"""Persistence for
:class:`core.models.delivery_slot_reservation.DeliverySlotReservation`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.delivery_slot_reservation import DeliverySlotReservation


class DeliverySlotReservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, reservation_id: uuid.UUID) -> DeliverySlotReservation | None:
        return await self._session.get(DeliverySlotReservation, reservation_id)

    async def list_for_slot(self, slot_id: uuid.UUID) -> list[DeliverySlotReservation]:
        stmt = select(DeliverySlotReservation).where(DeliverySlotReservation.slot_id == slot_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, reservation: DeliverySlotReservation) -> DeliverySlotReservation:
        self._session.add(reservation)
        await self._session.flush()
        return reservation

    async def update(self, reservation: DeliverySlotReservation) -> DeliverySlotReservation:
        await self._session.flush()
        return reservation
