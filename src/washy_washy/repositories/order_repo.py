"""Persistence for :class:`core.models.order.Order`.

``try_transition`` is the only place ``status`` is ever written by a
state-machine move — a single atomic conditional ``UPDATE``, the same
pattern as ``PickupSlotRepository.try_reserve_capacity`` (Phase 7).
That one statement is what makes concurrent transition attempts safe:
whichever request's ``UPDATE`` commits first wins, and the loser's
``WHERE`` clause simply matches zero rows instead of both overwriting
each other's work.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        return await self._session.get(Order, order_id)

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[Order]:
        stmt = select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, order: Order) -> Order:
        self._session.add(order)
        await self._session.flush()
        return order

    async def update(self, order: Order) -> Order:
        await self._session.flush()
        return order

    async def try_transition(self, order_id: uuid.UUID, from_status: str, to_status: str) -> bool:
        """Atomically moves ``status`` from ``from_status`` to
        ``to_status`` only if it's still ``from_status`` right now.
        Returns whether it succeeded — ``False`` means someone else
        already changed it since the caller last read it, not an error.
        """
        stmt = (
            update(Order)
            .where(Order.id == order_id, Order.status == from_status)
            .values(status=to_status)
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1
