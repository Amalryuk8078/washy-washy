"""RolePermission — associates a Role with a Permission."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.permission import Permission
    from core.models.role import Role


class RolePermission(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A single (role, permission) grant.

    Same rationale as :class:`core.models.user_role.UserRole`: immutable
    once created (no ``updated_at``), ``ON DELETE CASCADE`` only flows
    parent -> association, and the ``(role_id, permission_id)`` database
    constraint — not an application-level check — is the real guard
    against a duplicate grant under concurrent requests.
    """

    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[Role] = relationship("Role", back_populates="role_permissions")
    permission: Mapped[Permission] = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint(
            "role_id", "permission_id", name="uq_role_permissions_role_id_permission_id"
        ),
        # The composite unique constraint indexes (role_id, permission_id),
        # covering "permissions for this role" via its leading column.
        # "Roles containing this permission" filters on permission_id
        # alone, which needs its own index.
        Index("ix_role_permissions_permission_id", "permission_id"),
    )
