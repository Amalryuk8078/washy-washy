"""Persistence for :class:`core.models.order_status_history.OrderStatusHistory`.

Append-only: there is deliberately no ``update``/``delete`` here — an
audit trail is written once per transition and never edited.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.order_status_history import OrderStatusHistory


class OrderStatusHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_order(self, order_id: uuid.UUID) -> list[OrderStatusHistory]:
        stmt = (
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entry: OrderStatusHistory) -> OrderStatusHistory:
        self._session.add(entry)
        await self._session.flush()
        return entry
