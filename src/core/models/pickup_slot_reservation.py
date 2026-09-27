"""PickupSlotReservation — a customer's claim on part of a PickupSlot's
capacity.

No ``partner_profile_id`` here on purpose: a reservation is against the
service area's slot capacity, not a specific partner — *which* partner
fulfills it is an assignment decision (Phase 9), a separate concern from
*whether the slot has room* (this phase). No ``order_id`` either: Order
doesn't exist until Phase 8, which will be the one to link a reservation
to an order once it can.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ReservationStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class PickupSlotReservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pickup_slot_reservations"

    slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pickup_slots.id", ondelete="CASCADE"), nullable=False
    )
    customer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    capacity_used: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReservationStatus.ACTIVE,
        server_default=ReservationStatus.ACTIVE.value,
    )
