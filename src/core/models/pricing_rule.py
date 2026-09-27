"""PricingRule — the versioned base rate for a service.

Each row *is* a version: creating a new price for a service closes the
currently-active row (sets its `effective_to`) and inserts a new one
with `effective_from = now()`. A price change therefore never rewrites
an existing row's `base_price`/`unit_price` — it only ever adds a new
row and closes the old one — so a price computed under an old rule
stays correct forever, even after the rate changes. Persisting *which*
rule version produced a given historical price is Phase 8's job (an
`OrderItem` snapshotting `pricing_rule_id`), once orders exist.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PricingModel(enum.StrEnum):
    """How `unit_price` combines with quantity/weight to produce the
    quantity charge. Plain string column, not DB-enforced, so a new
    model doesn't need a migration.
    """

    PER_ITEM = "PER_ITEM"
    PER_KG = "PER_KG"
    PER_BAG = "PER_BAG"
    BASE_PLUS_WEIGHT = "BASE_PLUS_WEIGHT"
    CUSTOM = "CUSTOM"


class PricingRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One version of a service's base pricing.

    At most one *active* (``effective_to IS NULL``) rule per service —
    enforced by the partial unique index below, the same pattern as
    ``Address``'s one-default-per-user index in Phase 4.
    """

    __tablename__ = "pricing_rules"

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    pricing_model: Mapped[str] = mapped_column(String(20), nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_pricing_rules_one_active_per_service",
            "service_id",
            unique=True,
            postgresql_where=text("effective_to IS NULL"),
        ),
        # Supports "the rule active for this service at time T" lookups
        # (effective_from <= T AND (effective_to IS NULL OR effective_to > T)),
        # not just "the currently active one".
        Index("ix_pricing_rules_service_id_effective_from", "service_id", "effective_from"),
    )
