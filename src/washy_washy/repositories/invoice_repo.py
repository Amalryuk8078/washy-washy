"""Persistence for :class:`core.models.invoice.Invoice`.

``try_apply_payment``/``release_payment`` are the only places
``amount_paid`` is ever written — both single atomic conditional
``UPDATE`` statements, the same pattern as
``PickupSlotRepository.try_reserve_capacity`` (Phase 7) and
``OrderRepository.try_transition`` (Phase 8). That's what actually
prevents an invoice from ever being recorded as overpaid, regardless
of how many payments capture concurrently.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.invoice import Invoice


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        return await self._session.get(Invoice, invoice_id)

    async def get_by_order_id(self, order_id: uuid.UUID) -> Invoice | None:
        stmt = select(Invoice).where(Invoice.order_id == order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, invoice: Invoice) -> Invoice:
        self._session.add(invoice)
        await self._session.flush()
        return invoice

    async def update(self, invoice: Invoice) -> Invoice:
        await self._session.flush()
        return invoice

    async def try_apply_payment(self, invoice_id: uuid.UUID, amount: Decimal) -> bool:
        """Atomically increases ``amount_paid`` by ``amount`` only if
        doing so wouldn't exceed ``total``. Returns whether it
        succeeded.
        """
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == invoice_id,
                Invoice.amount_paid + amount <= Invoice.total,
            )
            .values(amount_paid=Invoice.amount_paid + amount)
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    async def release_payment(self, invoice_id: uuid.UUID, amount: Decimal) -> None:
        """The refund-side mirror of ``try_apply_payment`` — releases
        ``amount`` back off ``amount_paid`` (e.g. when a payment on
        this invoice is refunded). Unconditional, like
        ``PickupSlotRepository.release_capacity``: there's no upper
        bound to race against when giving capacity back.
        """
        stmt = (
            update(Invoice)
            .where(Invoice.id == invoice_id)
            .values(amount_paid=Invoice.amount_paid - amount)
        )
        await self._session.execute(stmt)
