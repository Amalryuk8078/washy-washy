"""Permission model.

A permission is ``resource + action + scope``. This module documents and
enforces one deliberate design decision (see ``PermissionScope`` below)
about how ``scope`` relates to the ``action`` vocabulary, since the two
can otherwise say contradictory things about the same permission.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.role_permission import RolePermission


class PermissionScope(enum.StrEnum):
    """Whose records a permission applies to.

    Design decision (documented here, not left implicit): the action
    vocabulary already encodes scope in its name for some actions
    (``READ_OWN``, ``READ_ASSIGNED``, ``READ_ALL``, ``UPDATE_OWN``,
    ``UPDATE_ASSIGNED``, ``UPDATE_ALL``). Rather than let ``scope`` be a
    second, independently-settable field that could contradict that
    suffix, ``scope`` for those actions must always be set to match it
    exactly (e.g. ``action="READ_OWN"`` implies ``scope="OWN"``). For
    actions whose name carries no scope (``CREATE``, ``ASSIGN``,
    ``REASSIGN``, ``APPROVE``, ``CANCEL``, ``OVERRIDE``) — which in this
    system are inherently administrative/global — ``scope`` is ``ALL``.

    This keeps ``scope`` always populated (never NULL), which is what
    lets ``(resource, action, scope)`` work as a real, enforceable
    uniqueness constraint: a NULL-able ``scope`` column would let
    PostgreSQL silently accept duplicate ``(resource, action, NULL)``
    rows, since NULLs are never equal to each other under a standard
    UNIQUE constraint.
    """

    OWN = "OWN"
    ASSIGNED = "ASSIGNED"
    ALL = "ALL"


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "resource", "action", "scope", name="uq_permissions_resource_action_scope"
        ),
        CheckConstraint("scope IN ('OWN', 'ASSIGNED', 'ALL')", name="valid_scope"),
    )
