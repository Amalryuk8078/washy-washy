"""Material — a fabric/material type (Cotton, Silk, Wool, Denim,
Synthetic, Leather, ...).

Catalog-level reference list only. The distinction between a customer's
*declared* material at booking time and the facility's *verified*
material after inspection (final pricing happens only after that
verification) is an ``OrderItem`` concern for Phase 8 — this table is
just the shared vocabulary both of those future fields will point at,
not a place to model that distinction itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.service_material import ServiceMaterial


class Material(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "materials"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    service_materials: Mapped[list[ServiceMaterial]] = relationship(
        "ServiceMaterial",
        back_populates="material",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
