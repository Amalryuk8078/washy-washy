"""PartnerCapability — which services a partner/facility can perform.

Capability only — *can* a partner perform a service at all — never
capacity (how much work they can currently take on) or scheduling.
Those are Phase 7's job; this table exists purely so Phase 7 (and
later, order assignment in Phase 8/9) has something to query.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.partner_profile import PartnerProfile
    from core.models.service import Service


class PartnerCapability(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A (partner, service) grant.

    Immutable once created (no ``updated_at``) — same reasoning as
    ``UserRole``/``RolePermission`` in Phase 1: a partner either can
    perform a service or can't; there's no in-between state to edit,
    only grant or revoke. ``ON DELETE CASCADE`` on both foreign keys,
    flowing only parent -> grant, same as those association tables.
    """

    __tablename__ = "partner_capabilities"

    partner_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )

    partner_profile: Mapped[PartnerProfile] = relationship(
        "PartnerProfile", back_populates="capabilities"
    )
    service: Mapped[Service] = relationship("Service", back_populates="partner_capabilities")

    __table_args__ = (
        UniqueConstraint(
            "partner_profile_id",
            "service_id",
            name="uq_partner_capabilities_partner_profile_id_service_id",
        ),
        Index("ix_partner_capabilities_service_id", "service_id"),
    )
