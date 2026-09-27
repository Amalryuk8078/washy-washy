"""OperatingHours — when a service area is open, per day of week.

A row's ``is_active = False`` represents a recurring closed day (e.g.
"we never operate on Sundays in this area") — there is no separate
holiday/exception-date calendar; that would be extra unasked-for
structure ahead of a real need for date-specific overrides.
"""

from __future__ import annotations

import enum
import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DayOfWeek(enum.StrEnum):
    """Plain string column, not DB-enforced — shared by
    ``OperatingHours`` and ``PartnerAvailability``.
    """

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class OperatingHours(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One (service area, day of week) opening window. At most one row
    per (service_area_id, day_of_week) — a second window on the same
    day isn't supported in this phase (no concrete need for it yet).
    """

    __tablename__ = "operating_hours"

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[str] = mapped_column(String(10), nullable=False)
    opening_time: Mapped[time] = mapped_column(Time, nullable=False)
    closing_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        UniqueConstraint(
            "service_area_id",
            "day_of_week",
            name="uq_operating_hours_service_area_id_day_of_week",
        ),
    )
