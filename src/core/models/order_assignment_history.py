"""OrderAssignmentHistory — an append-only audit trail of who was
assigned to an order, mirroring `OrderStatusHistory` (Phase 8) exactly:
same `CreatedAtMixin` (no `updated_at` — written once, never edited),
same `ON DELETE SET NULL` on the acting user (an audit trail should
survive the actor's account being deleted, not disappear with it).

`previous_assignee_id`/`new_assignee_id` are deliberately **plain
UUID columns, not foreign keys** — which table they point into depends
on `assignment_role` (a `PartnerFacility` id for `FACILITY`, a `User`
id for either operator role). A single FK can't target two different
tables, and a real polymorphic-association table would be over-
engineering for what is, in practice, always exactly one of two shapes.
This is an audit record of what the value *was*, not a live reference
that needs to keep resolving forever.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class AssignmentRole(enum.StrEnum):
    """Which of an order's three assignment slots changed. Plain string
    column, not DB-enforced — same reasoning as every other StrEnum in
    this project (`OrderStatus`, `DayOfWeek`, ...).
    """

    FACILITY = "FACILITY"
    PICKUP_OPERATOR = "PICKUP_OPERATOR"
    DELIVERY_OPERATOR = "DELIVERY_OPERATOR"


class OrderAssignmentHistory(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "order_assignment_history"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    assignment_role: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    new_assignee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
