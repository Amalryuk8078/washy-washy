"""MaterialPricingRule — the versioned price adjustment for a material.

Same versioning shape as ``PricingRule`` (see its docstring for the
"why"), applied to materials instead of services: a material's cost
(e.g. silk needing pricier solvent) can change independently of any
particular service's base rate.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MaterialPricingRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "material_pricing_rules"

    material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    price_adjustment: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_material_pricing_rules_one_active_per_material",
            "material_id",
            unique=True,
            postgresql_where=text("effective_to IS NULL"),
        ),
        Index(
            "ix_material_pricing_rules_material_id_effective_from",
            "material_id",
            "effective_from",
        ),
    )
