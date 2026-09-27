"""ServiceMaterial — which materials a service supports, plus any
care/handling requirements specific to that (service, material) pair
(e.g. wool under Wash needs a lower max temperature than cotton does).

Uses ``TimestampMixin`` (mutable, with ``updated_at``), not
``CreatedAtMixin`` — unlike a pure yes/no grant (``UserRole``,
``PartnerCapability``), this row carries real content (care
instructions, temperature) that legitimately gets corrected/updated in
place over time, not just granted or revoked.

Deliberately simple: two optional fields, not a rules engine. Extend
this table's columns if a real, concrete new requirement shows up
rather than generalizing ahead of one.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.material import Material
    from core.models.service import Service


class ServiceMaterial(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_materials"

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    care_instructions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    max_temperature_celsius: Mapped[int | None] = mapped_column(Integer, nullable=True)

    service: Mapped[Service] = relationship("Service", back_populates="service_materials")
    material: Mapped[Material] = relationship("Material", back_populates="service_materials")

    __table_args__ = (
        UniqueConstraint(
            "service_id", "material_id", name="uq_service_materials_service_id_material_id"
        ),
        # (service_id, material_id) covers "materials for this service"
        # via its leading column; "services supporting this material"
        # filters on material_id alone and needs its own index.
        Index("ix_service_materials_material_id", "material_id"),
    )
