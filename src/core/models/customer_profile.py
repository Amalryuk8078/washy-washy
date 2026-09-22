"""CustomerProfile — customer-facing profile data, kept separate from
User identity.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CustomerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One customer-facing profile per user.

    Does not duplicate anything already on `User` (email, password_hash,
    is_active, ...) — only fields specific to being a customer live
    here. Profile existence is independent of role assignment: creating
    this profile doesn't grant the ``CUSTOMER`` role, and holding that
    role doesn't require this profile to exist. A role grants
    permissions; a profile holds domain data. They're related concepts,
    not the same one.
    """

    __tablename__ = "customer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
