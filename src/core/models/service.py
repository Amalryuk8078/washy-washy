"""Service — a catalog offering (Wash, Dry Clean, Iron, Wash + Iron,
Express, ...).

Plain string ``name``, not a Python/DB enum: the business adds new
service types over time and that shouldn't require a migration. No
``ServiceCategory``/hierarchy either — the example services given don't
naturally group into anything beyond the flat list, and a hierarchy
with nothing to organize would just be unused structure (per the "avoid
unnecessary hierarchy" guidance). Add one later if a real need for
grouping shows up.

Deliberately independent of pricing (Phase 6) and availability/capacity
(Phase 7) — this is only the catalog of what a service *is*, not what it
costs or when it can be booked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.partner_capability import PartnerCapability
    from core.models.service_material import ServiceMaterial


class Service(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    service_materials: Mapped[list[ServiceMaterial]] = relationship(
        "ServiceMaterial",
        back_populates="service",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    partner_capabilities: Mapped[list[PartnerCapability]] = relationship(
        "PartnerCapability",
        back_populates="service",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
