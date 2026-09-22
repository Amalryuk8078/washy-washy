"""Role model — the middle tier of the User -> UserRole -> Role ->
RolePermission -> Permission RBAC graph.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.role_permission import RolePermission
    from core.models.user_role import UserRole


class RoleName(enum.StrEnum):
    """The foundational business roles.

    Not enforced at the database level — ``roles.name`` is a plain
    string column so a new role can be added later without a migration.
    This enum exists so seed data and tests reference one canonical
    spelling instead of scattering role-name string literals.
    """

    CUSTOMER = "CUSTOMER"
    LAUNDRY_PARTNER = "LAUNDRY_PARTNER"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
