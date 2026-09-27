"""Order — the central Washy Washy workflow record.

``status`` drives the full pickup -> facility -> delivery lifecycle
(see ``OrderStatus`` below); the actual transition graph and its
concurrency-safe enforcement live in
``washy_washy/services/order_state_service.py``, not here — this model
only defines the legal *values*, not which moves between them are
allowed.

**Ownership vs. reference, a deliberate split in this model's foreign
keys**: ``customer_id`` is ``ON DELETE CASCADE`` (an order has no
meaning without the customer who placed it, same reasoning as
``Address.user_id``), but ``service_area_id``/``pickup_address_id``/
``delivery_address_id``/``pickup_slot_id``/``delivery_slot_id``/
``pickup_reservation_id``/``delivery_reservation_id`` deliberately have
**no** ``ondelete`` (default ``RESTRICT``) — an order is this
project's first genuinely significant business record, and silently
cascading it away because a customer deleted an old address or an admin
removed a slot would destroy operational/financial history for no
benefit. Deleting an address/slot that's still referenced by an order
should fail loudly, not quietly erase the order.

``pickup_slot_id``/``pickup_reservation_id`` are nullable: an order
starts in ``DRAFT`` with no slot chosen yet, and is only populated once
the customer/staff schedules a pickup (moving the order to
``PICKUP_SCHEDULED`` — see ``OrderService.schedule_pickup``). The
reservation id (as opposed to just the slot id) is what
``OrderService``/cancellation flows need to release the slot's capacity
through ``AvailabilityService`` (Phase 7) — the slot id alone isn't
enough to identify *which* reservation to release.
``delivery_slot_id``/``delivery_reservation_id`` exist on the model per
the Phase 8 spec's field list, but no scheduling workflow populates
them yet — delivery scheduling is operational detail that belongs to
Phase 9 (Partner Operations).

**Phase 9 addendum — assignment columns.** ``assigned_facility_id``/
``pickup_operator_user_id``/``delivery_operator_user_id`` are
deliberately kept separate from scheduling (``pickup_slot_id`` etc.)
per the Phase 9 spec's own instruction: *who* is handling an order and
*when* it happens are independent concerns. ``assigned_facility_id``
has no ``ondelete`` (a reference, same reasoning as
``service_area_id``); the two operator columns are ``ON DELETE SET
NULL`` — a staff account being deleted should clear the assignment,
not silently cascade-delete the order or block the user's own
deletion. Every assignment/reassignment is recorded in
``OrderAssignmentHistory``, never overwritten silently.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OrderStatus(enum.StrEnum):
    """The full order lifecycle, plus its exception states.

    Plain string column, not DB-enforced (same reasoning as
    ``RoleName``/``PricingModel``/``DayOfWeek`` elsewhere) — the legal
    *transitions* between these are enforced in Python by
    ``order_state_service.py``, not by a database constraint.
    """

    DRAFT = "DRAFT"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    PICKUP_SCHEDULED = "PICKUP_SCHEDULED"
    PICKUP_ASSIGNED = "PICKUP_ASSIGNED"
    PICKUP_IN_PROGRESS = "PICKUP_IN_PROGRESS"
    PICKED_UP = "PICKED_UP"
    RECEIVED_AT_FACILITY = "RECEIVED_AT_FACILITY"
    INSPECTION = "INSPECTION"
    ITEMIZED = "ITEMIZED"
    PRICE_FINALIZED = "PRICE_FINALIZED"
    PROCESSING = "PROCESSING"
    QUALITY_CHECK = "QUALITY_CHECK"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    DELIVERY_ASSIGNED = "DELIVERY_ASSIGNED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PICKUP_FAILED = "PICKUP_FAILED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    PRICE_ADJUSTMENT_REQUIRED = "PRICE_ADJUSTMENT_REQUIRED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id"), nullable=False
    )
    pickup_address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id"), nullable=False)
    delivery_address_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("addresses.id"), nullable=False
    )
    pickup_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pickup_slots.id"), nullable=True
    )
    delivery_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_slots.id"), nullable=True
    )
    pickup_reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pickup_slot_reservations.id"), nullable=True
    )
    delivery_reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_slot_reservations.id"), nullable=True
    )
    assigned_facility_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("partner_facilities.id"), nullable=True
    )
    pickup_operator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    delivery_operator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=OrderStatus.DRAFT.value,
        server_default=OrderStatus.DRAFT.value,
    )
    estimated_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    final_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        CheckConstraint("estimated_total >= 0", name="estimated_total_non_negative"),
        CheckConstraint("final_total IS NULL OR final_total >= 0", name="final_total_non_negative"),
    )
