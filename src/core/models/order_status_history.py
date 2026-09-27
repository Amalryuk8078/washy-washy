"""OrderStatusHistory — an append-only audit trail of every order state
transition.

Uses ``CreatedAtMixin`` (no ``updated_at``) — same reasoning as
``UserRole``/``RolePermission`` in Phase 1: a history row is written
once and never edited in place. Every write goes through
``OrderStateService.transition``, in the same database transaction as
the order's own status ``UPDATE`` (see
``washy_washy/repositories/order_repo.py::try_transition``) — the two
are never committed as separate, independently-failable operations.

``changed_by_user_id`` uses ``ON DELETE SET NULL``, not ``CASCADE`` —
deliberately different from every other user-owned FK in this project.
An audit trail's whole purpose is to survive; if the actor's account is
ever deleted, the historical record should keep existing with the actor
field cleared, not disappear along with them.

The DB column is named ``metadata`` per the Phase 8 spec's own field
list, but the Python/ORM attribute is ``extra_data`` — ``metadata`` is
a reserved attribute name on every SQLAlchemy declarative model
(``Base.metadata``), so mapping straight through would collide with it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class OrderStatusHistory(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_by_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
