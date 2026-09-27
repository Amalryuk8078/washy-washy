"""OrderItem — one service+material line within an order.

Deliberately separate from the order's own ``status`` (per the Phase 8
spec: "Do not mix order item state with order state") — an item has no
status of its own, only a declared/verified data pair and a pricing
snapshot pair.

**Declared vs. verified, kept as genuinely separate columns rather than
overwriting one with the other**: ``declared_material_id``/
``declared_quantity``/``declared_weight_kg`` are what the customer
entered at order creation; ``verified_material_id``/
``verified_quantity``/``verified_weight_kg`` are what the facility
confirms during inspection (``OrderService.itemize_order_item``). Both
sets stay visible after inspection so a customer's original declaration
is never silently lost.

**Pricing snapshot, not a live recomputation**: ``estimated_pricing_rule_id``/
``estimated_material_pricing_rule_id``/``estimated_line_total`` capture
*which* versioned ``PricingRule``/``MaterialPricingRule`` row (Phase 6)
produced the estimate and what it came to; ``final_*`` mirror this for
the post-inspection price. Because ``PricingRule``/``MaterialPricingRule``
rows are themselves immutable once closed (Phase 6), a later rate change
can never retroactively alter what this item already charged — reading
this row never needs to re-run ``PricingService.calculate_price``.
These FK columns intentionally have no ``ondelete`` (default
``RESTRICT``): those rows are never deleted, so it's never triggered,
but a snapshot pointer should not silently go stale via a cascade
either way.

The two FKs to ``material_pricing_rules`` use an explicit, shorter
constraint name (``fk_order_items_est_material_rule_id``/
``fk_order_items_final_material_rule_id``) instead of the naming
convention's derived one, which would exceed PostgreSQL's 63-byte
identifier limit (the same class of problem that led to renaming
``partner_service_capabilities`` in Phase 5).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    declared_material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("materials.id"), nullable=False
    )
    verified_material_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("materials.id"), nullable=True
    )
    declared_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    declared_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    verified_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    estimated_pricing_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pricing_rules.id"), nullable=True
    )
    estimated_material_pricing_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("material_pricing_rules.id", name="fk_order_items_est_material_rule_id"),
        nullable=True,
    )
    estimated_line_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    final_pricing_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pricing_rules.id"), nullable=True
    )
    final_material_pricing_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("material_pricing_rules.id", name="fk_order_items_final_material_rule_id"),
        nullable=True,
    )
    final_line_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "estimated_line_total IS NULL OR estimated_line_total >= 0",
            name="estimated_line_total_non_negative",
        ),
        CheckConstraint(
            "final_line_total IS NULL OR final_line_total >= 0",
            name="final_line_total_non_negative",
        ),
    )
