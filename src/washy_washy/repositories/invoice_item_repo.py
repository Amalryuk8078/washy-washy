"""Persistence for :class:`core.models.invoice_item.InvoiceItem`.

Append-only: no ``update``/``delete`` here — an invoice line is written
once, when the invoice is created, and never edited afterward.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.invoice_item import InvoiceItem


class InvoiceItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[InvoiceItem]:
        stmt = (
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == invoice_id)
            .order_by(InvoiceItem.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, item: InvoiceItem) -> InvoiceItem:
        self._session.add(item)
        await self._session.flush()
        return item
