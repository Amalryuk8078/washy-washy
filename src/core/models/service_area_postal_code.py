"""ServiceAreaPostalCode — the actual geography backing a ServiceArea.

A separate one-to-many table (not a `postal_code` column on
`ServiceArea` itself) so one area can cover many postal codes, and so a
different boundary representation (city, polygon, ...) could be added
alongside this one later without reworking `ServiceArea`. See
`washy_washy/services/service_area_service.py` for the serviceability
check this exists to support.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base
from core.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.service_area import ServiceArea


class ServiceAreaPostalCode(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One postal code covered by a service area.

    A postal code belongs to at most one service area (`postal_code` is
    globally unique here, not just unique within its area) — two
    overlapping delivery zones both claiming the same postal code would
    make "which area serves this address" ambiguous. `ON DELETE CASCADE`
    on `service_area_id`: deleting a `ServiceArea` removes its postal
    code mappings, which have no meaning without it.
    """

    __tablename__ = "service_area_postal_codes"

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id", ondelete="CASCADE"), nullable=False
    )
    postal_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    service_area: Mapped[ServiceArea] = relationship("ServiceArea", back_populates="postal_codes")
