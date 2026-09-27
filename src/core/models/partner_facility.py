"""PartnerFacility — a physical site a partner operates from.

This is the model Phase 7's `AvailabilityService.has_capable_partner`
docstring predicted: "[a real capability check] requires a
`PartnerProfile <-> ServiceArea` association that doesn't exist yet ...
which is the natural place for that link" (Phase 9). `service_area_id`
below is exactly that link. Closing that gap for real (making
`has_capable_partner` actually area-scoped) is left to whichever future
work wires availability to assignment — this model only establishes
the association; it doesn't retroactively change Phase 7's behavior,
per "do not rewrite existing working code."

A facility carries its **own** address columns rather than a foreign
key to `addresses` — deliberately: `Address` (Phase 4) is scoped to
"one of a *user's own* pickup/delivery addresses," with `AddressService`
ownership checks built around that framing. A facility's location isn't
a user's own address in that sense; duplicating the handful of location
columns keeps the two concepts (personal address book vs. business
site) from bleeding into each other.

`daily_capacity` is **informational only, not enforced anywhere** — the
same "documented, not silently wrong" posture as `has_capable_partner`.
Actual booking capacity is still exclusively governed by Phase 7's
`PickupSlot`/`DeliverySlot.capacity_total`; this field does not create
a second, competing source of truth for how much a facility can
handle.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PartnerFacility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_facilities"

    partner_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="CASCADE"), nullable=False
    )
    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    daily_capacity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        UniqueConstraint(
            "partner_profile_id", "name", name="uq_partner_facilities_partner_profile_id_name"
        ),
    )
