"""Payment — money collected against an invoice.

``ON DELETE CASCADE`` on ``invoice_id``: a payment has no meaning
without the invoice it's paying, the same ownership relationship
``InvoiceItem`` has to ``Invoice``.

``captured_amount``/``refunded_amount`` are bookkeeping columns kept in
sync by ``PaymentRepository``'s atomic conditional ``UPDATE``s
(``try_capture``/``try_refund``) — the same pattern as
``Invoice.amount_paid`` and Phase 7's slot capacity — never a
read-then-write from Python. The two ``CHECK`` constraints below are
the belt-and-suspenders database guard against any other code path
ever writing to this row a different way, not the primary mechanism.

``provider_reference`` is deliberately a plain nullable string, not a
foreign key to anything — it's an opaque id from whichever
``PaymentGateway`` implementation handled this payment (see
``washy_washy/payments/gateway.py``), which this project's own schema
has no reason to understand the shape of.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PaymentStatus(enum.StrEnum):
    """Plain string column, not DB-enforced — matches the Phase 10
    spec's own state list exactly.
    """

    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    VOIDED = "VOIDED"
    CANCELLED = "CANCELLED"
    PARTIALLY_PAID = "PARTIALLY_PAID"


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    captured_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentStatus.PENDING.value,
        server_default=PaymentStatus.PENDING.value,
    )
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint(
            "captured_amount >= 0 AND captured_amount <= amount",
            name="captured_within_amount",
        ),
        CheckConstraint(
            "refunded_amount >= 0 AND refunded_amount <= captured_amount",
            name="refunded_within_captured",
        ),
    )
