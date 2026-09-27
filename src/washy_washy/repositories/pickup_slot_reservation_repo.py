"""Persistence for
:class:`core.models.pickup_slot_reservation.PickupSlotReservation`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.pickup_slot_reservation import PickupSlotReservation


class PickupSlotReservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, reservation_id: uuid.UUID) -> PickupSlotReservation | None:
        return await self._session.get(PickupSlotReservation, reservation_id)

    async def list_for_slot(self, slot_id: uuid.UUID) -> list[PickupSlotReservation]:
        stmt = select(PickupSlotReservation).where(PickupSlotReservation.slot_id == slot_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, reservation: PickupSlotReservation) -> PickupSlotReservation:
        self._session.add(reservation)
        await self._session.flush()
        return reservation

    async def update(self, reservation: PickupSlotReservation) -> PickupSlotReservation:
        await self._session.flush()
        return reservation
