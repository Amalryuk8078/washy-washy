"""Persistence for :class:`core.models.refund.Refund`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.refund import Refund


class RefundRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, refund_id: uuid.UUID) -> Refund | None:
        return await self._session.get(Refund, refund_id)

    async def list_for_payment(self, payment_id: uuid.UUID) -> list[Refund]:
        stmt = select(Refund).where(Refund.payment_id == payment_id).order_by(Refund.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, refund: Refund) -> Refund:
        self._session.add(refund)
        await self._session.flush()
        return refund

    async def update(self, refund: Refund) -> Refund:
        await self._session.flush()
        return refund
