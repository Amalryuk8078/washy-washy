"""DeliverySlotReservation — a customer's claim on part of a
DeliverySlot's capacity. Mirrors ``PickupSlotReservation`` exactly; see
its docstring for why there's no ``partner_profile_id``/``order_id``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from core.models.pickup_slot_reservation import ReservationStatus


class DeliverySlotReservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_slot_reservations"

    slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_slots.id", ondelete="CASCADE"), nullable=False
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
