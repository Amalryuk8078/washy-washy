"""Persistence for
:class:`core.models.order_assignment_history.OrderAssignmentHistory`.

Append-only: same posture as ``order_status_history_repo.py`` — no
``update``/``delete``, a record is written once and never edited.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.order_assignment_history import OrderAssignmentHistory


class OrderAssignmentHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_order(self, order_id: uuid.UUID) -> list[OrderAssignmentHistory]:
        stmt = (
            select(OrderAssignmentHistory)
            .where(OrderAssignmentHistory.order_id == order_id)
            .order_by(OrderAssignmentHistory.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entry: OrderAssignmentHistory) -> OrderAssignmentHistory:
        self._session.add(entry)
        await self._session.flush()
        return entry
