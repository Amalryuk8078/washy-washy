"""PaymentAttempt — one try at charging a payment through the gateway.

Uses ``TimestampMixin`` (mutable), not ``CreatedAtMixin`` — deliberately
different from ``PaymentEvent`` below. An attempt is created ``PENDING``
and then *resolves* to a terminal state (``CAPTURED``/``FAILED``) as
the same row, not a new one; there is exactly one row per real attempt
to charge, and its outcome is recorded in place. Retrying after a
failure creates a genuinely new attempt row (a second try), not a
mutation of the first.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PaymentAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_attempts"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
