"""Persistence for :class:`core.models.order_item.OrderItem`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.order_item import OrderItem


class OrderItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: uuid.UUID) -> OrderItem | None:
        return await self._session.get(OrderItem, item_id)

    async def list_for_order(self, order_id: uuid.UUID) -> list[OrderItem]:
        stmt = (
            select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, item: OrderItem) -> OrderItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def update(self, item: OrderItem) -> OrderItem:
        await self._session.flush()
        return item
