"""PickupSlot — a bookable pickup time window for a service area, with
its own capacity.

Kept as a genuinely separate table from ``DeliverySlot`` (not one
polymorphic "slot" table with a type column) — a future ``Order``'s
``pickup_slot_id``/``delivery_slot_id`` must be unambiguous foreign keys
to distinct tables, per the Phase 7 spec's explicit "do not use one
slot field for both."

``capacity_reserved`` is only ever changed via
``PickupSlotRepository.try_reserve_capacity``'s single atomic
conditional ``UPDATE`` (``WHERE capacity_reserved + :amount <=
capacity_total``) — never a read-then-write from application code. That
one statement is what actually prevents two concurrent bookings from
both succeeding and overbooking the slot; the ``CHECK`` constraint below
is a second, belt-and-suspenders guard against any other code path ever
writing to this row a different way.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PickupSlot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pickup_slots"

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id", ondelete="CASCADE"), nullable=False
    )
    slot_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    capacity_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    capacity_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    capacity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        UniqueConstraint(
            "service_area_id",
            "slot_date",
            "start_time",
            "end_time",
            name="uq_pickup_slots_area_date_start_end",
        ),
        CheckConstraint("capacity_reserved <= capacity_total", name="capacity_within_total"),
        CheckConstraint("capacity_reserved >= 0", name="capacity_reserved_non_negative"),
    )
