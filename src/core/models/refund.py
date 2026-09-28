"""Refund — money returned against a specific payment.

``ON DELETE CASCADE`` on ``payment_id``: a refund has no meaning
without the payment it's refunding.

"Never refund more than the captured amount" (the spec's own words) is
enforced the same way every other capacity-style invariant in this
project is: ``PaymentRepository.try_refund``'s single atomic
conditional ``UPDATE`` on ``Payment.refunded_amount``
(``WHERE refunded_amount + :amount <= captured_amount``), not a
read-then-write from Python — see ``Payment``'s own docstring. This
row is only ever created *after* that ``UPDATE`` already succeeded, so
its mere existence is proof the invariant held at the moment of
creation.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RefundStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class Refund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refunds"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=RefundStatus.PENDING.value,
        server_default=RefundStatus.PENDING.value,
    )
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)
