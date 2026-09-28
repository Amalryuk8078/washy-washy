"""Invoice — the amount owed for an order, strictly separate from the
order's own operational workflow (per the Phase 10 spec's own framing:
``ORDER -> operational workflow``, ``INVOICE -> amount owed``,
``PAYMENT -> money collected``, ``REFUND -> money returned``).

``ON DELETE CASCADE`` on ``order_id``: unlike `Order`'s own references
to independent resources (addresses, slots — see `Order`'s docstring),
an invoice has no meaning without the order it bills, the same
ownership relationship `OrderItem`/`OrderStatusHistory` have to
`Order`. One invoice per order (`UNIQUE` on ``order_id``) — this
project never re-issues a second invoice for the same order; a
correction goes through a refund, not a second bill.

**Immutability after finalization** is enforced by *omission*, not by
a runtime check: no service method exists that can alter
``subtotal``/``tax``/``discount``/``total`` once ``status`` leaves
``DRAFT``. There's nothing to "silently mutate" because nothing here
can mutate it at all — the spec's own "do not silently mutate finalized
invoice totals," taken literally.

``amount_paid`` is only ever changed via
``InvoiceRepository.try_apply_payment``'s atomic conditional ``UPDATE``
(mirroring Phase 7's ``try_reserve_capacity``/Phase 8's
``try_transition`` exactly) — never a read-then-write from Python. That
one statement is what actually prevents an invoice from ever being
overpaid under concurrent captures.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InvoiceStatus(enum.StrEnum):
    """Plain string column, not DB-enforced — same reasoning as every
    other StrEnum in this project.
    """

    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    VOID = "VOID"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InvoiceStatus.DRAFT.value,
        server_default=InvoiceStatus.DRAFT.value,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("total >= 0", name="total_non_negative"),
        CheckConstraint("amount_paid >= 0", name="amount_paid_non_negative"),
        CheckConstraint("amount_paid <= total", name="amount_paid_within_total"),
    )
