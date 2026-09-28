"""Persistence for :class:`core.models.payment_attempt.PaymentAttempt`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.payment_attempt import PaymentAttempt


class PaymentAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_payment(self, payment_id: uuid.UUID) -> list[PaymentAttempt]:
        stmt = (
            select(PaymentAttempt)
            .where(PaymentAttempt.payment_id == payment_id)
            .order_by(PaymentAttempt.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, attempt: PaymentAttempt) -> PaymentAttempt:
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def update(self, attempt: PaymentAttempt) -> PaymentAttempt:
        await self._session.flush()
        return attempt
