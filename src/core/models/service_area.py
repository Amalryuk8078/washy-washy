"""ServiceArea — where Washy Washy operates.

Deliberately holds no geography itself (no `postal_code` column here) —
see `core/models/service_area_postal_code.py` for why: a single
representation (one area = one postal code) would need reworking the
moment the business needs an area covering several postal codes, or a
different kind of boundary (city, polygon, ...) entirely.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.service_area_postal_code import ServiceAreaPostalCode


class ServiceArea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_areas"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    postal_codes: Mapped[list[ServiceAreaPostalCode]] = relationship(
        "ServiceAreaPostalCode",
        back_populates="service_area",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
