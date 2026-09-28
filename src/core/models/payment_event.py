"""PaymentEvent — an append-only, auditable log of every event this
project has received about a payment (webhook deliveries first and
foremost), and the concrete mechanism behind the Phase 10 spec's
"webhook processing must be idempotent" requirement.

``provider_event_id`` carries a real, database-level ``UNIQUE``
constraint — not just an application-level existence check. A gateway
retrying the same webhook delivery (which every real provider does)
produces a second `INSERT` with the same ``provider_event_id``; the
unique constraint rejects it as an ``IntegrityError``, which the
service layer catches and turns into a silent no-op, exactly the same
"the database constraint is the real guard, not application logic"
posture as ``UserRole``'s `(user_id, role_id)` uniqueness (Phase 1) and
every other duplicate-prevention mechanism in this project.

Uses ``CreatedAtMixin`` (no ``updated_at``) — an event is a fact that
happened; it is never edited after being recorded, only ever read.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class PaymentEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "payment_events"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_payment_events_provider_event_id"),
    )
