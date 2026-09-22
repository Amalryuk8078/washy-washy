"""PartnerProfile — laundry-partner-facing profile data, kept separate
from User identity and from authentication concerns.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PartnerStatus(enum.StrEnum):
    """A partner's onboarding/vetting lifecycle — distinct from
    ``User.is_active`` (an authentication-account flag, not a business
    one). A partner can be ``PENDING`` review while their login account
    is perfectly active. The full onboarding *workflow* is Phase 9's
    job; this is just the status field it will drive. Not DB-enforced
    (plain string column) so a new status doesn't need a migration.
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class PartnerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One partner-facing profile per user.

    Same "no auth/identity duplication" rule as
    :class:`core.models.customer_profile.CustomerProfile`. Business
    contact details are intentionally separate from the account owner's
    personal login email/phone on `User`.
    """

    __tablename__ = "partner_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PartnerStatus.PENDING,
        server_default=PartnerStatus.PENDING.value,
    )
