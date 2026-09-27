"""Persistence for :class:`core.models.pickup_slot.PickupSlot`.

``try_reserve_capacity``/``release_capacity`` are the only places
``capacity_reserved`` is ever written — both are single atomic
conditional ``UPDATE`` statements, not a read-then-write from Python.
See the model's docstring for why that's what actually prevents
overbooking under concurrent requests.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.pickup_slot import PickupSlot


class PickupSlotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, slot_id: uuid.UUID) -> PickupSlot | None:
        return await self._session.get(PickupSlot, slot_id)

    async def list_for_service_area(
        self, service_area_id: uuid.UUID, *, active_only: bool = True
    ) -> list[PickupSlot]:
        stmt = select(PickupSlot).where(PickupSlot.service_area_id == service_area_id)
        if active_only:
            stmt = stmt.where(PickupSlot.is_active.is_(True))
        stmt = stmt.order_by(PickupSlot.slot_date, PickupSlot.start_time)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, slot: PickupSlot) -> PickupSlot:
        self._session.add(slot)
        await self._session.flush()
        return slot

    async def try_reserve_capacity(self, slot_id: uuid.UUID, amount: Decimal) -> bool:
        """Atomically increments ``capacity_reserved`` by ``amount`` only
        if doing so wouldn't exceed ``capacity_total`` and the slot is
        active. Returns whether it succeeded — ``False`` means the slot
        didn't have room (or doesn't exist/isn't active), not an error.
        """
        stmt = (
            update(PickupSlot)
            .where(
                PickupSlot.id == slot_id,
                PickupSlot.is_active.is_(True),
                PickupSlot.capacity_reserved + amount <= PickupSlot.capacity_total,
            )
            .values(capacity_reserved=PickupSlot.capacity_reserved + amount)
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    async def release_capacity(self, slot_id: uuid.UUID, amount: Decimal) -> None:
        stmt = (
            update(PickupSlot)
            .where(PickupSlot.id == slot_id)
            .values(capacity_reserved=PickupSlot.capacity_reserved - amount)
        )
        await self._session.execute(stmt)
