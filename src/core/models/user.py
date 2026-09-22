"""User identity model.

Pure identity only: no ``role``/``role_id`` column (a user may hold more
than one role — see :class:`core.models.user_role.UserRole`) and no
domain profile fields (customer/partner profile data is a later phase's
model, kept separate from identity).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.user_role import UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An account that can authenticate into Washy Washy.

    Email uniqueness is enforced on the *stored* value: the repository
    layer (``washy_washy/repositories/user_repo.py``) normalizes every
    email to lowercase, stripped, before it reaches this model, so
    ``Amal@Example.com`` and ``amal@example.com`` collide as intended.
    The database itself carries a plain (case-sensitive) UNIQUE
    constraint over that already-normalized value — no PostgreSQL
    ``citext`` extension needed for something the application already
    guarantees.

    ``phone`` is nullable; PostgreSQL's standard UNIQUE constraint
    already allows any number of NULLs alongside at most one occurrence
    of each non-NULL value, which is exactly the desired behavior here.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
