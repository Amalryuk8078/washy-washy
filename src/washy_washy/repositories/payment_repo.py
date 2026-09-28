"""Persistence for :class:`core.models.payment.Payment`.

``try_capture``/``try_refund`` are the only places
``captured_amount``/``refunded_amount`` are ever written — single
atomic conditional ``UPDATE`` statements, the same pattern used
throughout this project (Phase 7's slot capacity, Phase 8's order
transitions, ``InvoiceRepository.try_apply_payment`` above).
``try_refund`` in particular is the concrete mechanism behind the spec's
"never refund more than the captured amount" — the check and the
increment happen in the same statement, so two concurrent refund
requests can never both succeed past the captured amount.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.payment import Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        return await self._session.get(Payment, payment_id)

    async def get_by_provider_reference(self, provider_reference: str) -> Payment | None:
        stmt = select(Payment).where(Payment.provider_reference == provider_reference)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, payment: Payment) -> Payment:
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def update(self, payment: Payment) -> Payment:
        await self._session.flush()
        return payment

    async def try_capture(self, payment_id: uuid.UUID, amount: Decimal) -> bool:
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.captured_amount + amount <= Payment.amount,
            )
            .values(captured_amount=Payment.captured_amount + amount)
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    async def try_refund(self, payment_id: uuid.UUID, amount: Decimal) -> bool:
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.refunded_amount + amount <= Payment.captured_amount,
            )
            .values(refunded_amount=Payment.refunded_amount + amount)
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    async def release_refund(self, payment_id: uuid.UUID, amount: Decimal) -> None:
        """Unconditionally releases a ``try_refund`` reservation that
        was taken before calling the gateway, but the gateway call
        itself then failed -- the mirror of
        ``InvoiceRepository.release_payment``. Never used to represent
        a real, completed refund; that's what the ``Refund`` row
        itself records.
        """
        stmt = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(refunded_amount=Payment.refunded_amount - amount)
        )
        await self._session.execute(stmt)
