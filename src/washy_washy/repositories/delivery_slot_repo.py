"""Persistence for :class:`core.models.delivery_slot.DeliverySlot`.
Mirrors ``PickupSlotRepository`` exactly — see its docstring for why
``try_reserve_capacity``/``release_capacity`` are atomic conditional
``UPDATE``s.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.delivery_slot import DeliverySlot


class DeliverySlotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, slot_id: uuid.UUID) -> DeliverySlot | None:
        return await self._session.get(DeliverySlot, slot_id)

    async def list_for_service_area(
        self, service_area_id: uuid.UUID, *, active_only: bool = True
    ) -> list[DeliverySlot]:
        stmt = select(DeliverySlot).where(DeliverySlot.service_area_id == service_area_id)
        if active_only:
            stmt = stmt.where(DeliverySlot.is_active.is_(True))
        stmt = stmt.order_by(DeliverySlot.slot_date, DeliverySlot.start_time)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, slot: DeliverySlot) -> DeliverySlot:
        self._session.add(slot)
        await self._session.flush()
        return slot

    async def try_reserve_capacity(self, slot_id: uuid.UUID, amount: Decimal) -> bool:
        stmt = (
            update(DeliverySlot)
            .where(
                DeliverySlot.id == slot_id,
                DeliverySlot.is_active.is_(True),
                DeliverySlot.capacity_reserved + amount <= DeliverySlot.capacity_total,
            )
            .values(capacity_reserved=DeliverySlot.capacity_reserved + amount)
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    async def release_capacity(self, slot_id: uuid.UUID, amount: Decimal) -> None:
        stmt = (
            update(DeliverySlot)
            .where(DeliverySlot.id == slot_id)
            .values(capacity_reserved=DeliverySlot.capacity_reserved - amount)
        )
        await self._session.execute(stmt)
