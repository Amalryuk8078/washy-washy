"""PartnerAvailability — when a partner/facility can accept work, per
day of week.

Distinct from ``PartnerCapability`` (Phase 5: *which services* a
partner can perform) and from partner *assignment* (Phase 9: assigning
a specific order to a specific partner) — this is only "is this partner
generally working during this window," a yes/no schedule, not a
capacity number (that's explicitly out of scope per the Phase 7 spec)
and not a decision about any particular order.
"""

from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PartnerAvailability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One (partner, day of week) availability window. At most one row
    per (partner_profile_id, day_of_week), same reasoning as
    ``OperatingHours``.
    """

    __tablename__ = "partner_availabilities"

    partner_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        UniqueConstraint(
            "partner_profile_id",
            "day_of_week",
            name="uq_partner_availabilities_partner_profile_id_day_of_week",
        ),
    )
