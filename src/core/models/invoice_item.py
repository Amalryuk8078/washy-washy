"""InvoiceItem — one immutable, snapshotted line on an invoice.

Uses ``CreatedAtMixin`` (no ``updated_at``) — an invoice item is
written once, when the invoice is created from the order's finalized
items, and never edited in place afterward; that's what "immutable
pricing snapshot" (the spec's own phrase) means concretely here.
``order_item_id`` is a plain reference (no ``ondelete``) back to the
``OrderItem`` this line came from, for traceability — deleting an
order item doesn't happen in practice (orders aren't hard-deleted) so
this is never triggered, but it should fail loudly rather than
silently orphan a billed line if it ever were.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class InvoiceItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
