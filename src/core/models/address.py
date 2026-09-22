"""Address — a user can have several; never stored inline on User."""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AddressLabel(enum.StrEnum):
    """Suggested (not DB-enforced) labels — `addresses.label` is a plain
    string column so a client can send something else (e.g. "Gym",
    "Parents' House") without a migration; these are just the common
    ones referenced by seed data/tests.
    """

    HOME = "HOME"
    WORK = "WORK"
    OTHER = "OTHER"


class Address(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A pickup/delivery address belonging to a user.

    ``ON DELETE CASCADE`` on ``user_id``: an address has no meaning
    without the user who owns it, so deleting the user removes their
    addresses too (unlike the RBAC association tables in Phase 1, this
    is genuinely owned data, not a many-to-many grant).

    At most one address per user may have ``is_default = true`` —
    enforced by the partial unique index below, not just application
    logic (see ``washy_washy/services/address_service.py`` for the
    transaction-safe "set as default" operation that flips the old
    default off and the new one on).
    """

    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        # "List addresses for this user" is the real query pattern —
        # address lookups are never by postal code/city across users.
        Index("ix_addresses_user_id", "user_id"),
        Index(
            "uq_addresses_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )
