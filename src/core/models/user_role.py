"""UserRole — associates a User with a Role (a user may hold several)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.role import Role
    from core.models.user import User


class UserRole(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A single (user, role) grant.

    Immutable once created — see :class:`core.models.mixins.CreatedAtMixin`
    for why there is no ``updated_at``: an assignment exists or it
    doesn't, it is never edited in place.

    ``ON DELETE CASCADE`` on both foreign keys is intentional and only
    ever flows parent -> association: deleting a User or Role removes
    their now-meaningless role assignments, but deleting a UserRole row
    can never delete the User or Role it references. The database
    constraint on ``(user_id, role_id)`` — not an application-level
    existence check — is what actually prevents a duplicate assignment
    under concurrent requests.
    """

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="user_roles")
    role: Mapped[Role] = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_id_role_id"),
        # The composite unique constraint above already indexes
        # (user_id, role_id), which covers "roles for this user" lookups
        # via its leading column. "Users for this role" lookups filter on
        # role_id alone, which that composite index can't serve
        # efficiently (role_id isn't the leading column) — hence this.
        Index("ix_user_roles_role_id", "role_id"),
    )
