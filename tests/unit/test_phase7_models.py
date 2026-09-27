"""Offline (no database) tests for the Phase 7 availability/slot model
definitions: OperatingHours, PartnerAvailability, PickupSlot,
DeliverySlot, PickupSlotReservation, DeliverySlotReservation.
"""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from core.models import (
    CapacityUnit,
    DayOfWeek,
    DeliverySlot,
    DeliverySlotReservation,
    OperatingHours,
    PartnerAvailability,
    PickupSlot,
    PickupSlotReservation,
    ReservationStatus,
)


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_day_of_week_has_seven_days() -> None:
    assert {d.value for d in DayOfWeek} == {
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
        "SATURDAY",
        "SUNDAY",
    }


def test_capacity_unit_matches_spec() -> None:
    assert {u.value for u in CapacityUnit} == {"ORDERS", "WEIGHT_KG", "ITEMS", "BAGS"}


def test_operating_hours_unique_per_area_and_day() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in OperatingHours.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("service_area_id", "day_of_week") in unique_columns


def test_partner_availability_unique_per_partner_and_day() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in PartnerAvailability.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("partner_profile_id", "day_of_week") in unique_columns


def test_pickup_and_delivery_slots_are_separate_tables() -> None:
    # The Phase 7 spec's explicit "do not use one slot field for both".
    assert PickupSlot.__tablename__ != DeliverySlot.__tablename__
    assert PickupSlot is not DeliverySlot


def test_pickup_and_delivery_reservations_are_separate_tables() -> None:
    assert PickupSlotReservation.__tablename__ != DeliverySlotReservation.__tablename__
    assert PickupSlotReservation is not DeliverySlotReservation


def test_pickup_slot_has_capacity_check_constraints() -> None:
    check_names = {
        con.name for con in PickupSlot.__table__.constraints if isinstance(con, CheckConstraint)
    }
    assert "ck_pickup_slots_capacity_within_total" in check_names
    assert "ck_pickup_slots_capacity_reserved_non_negative" in check_names


def test_pickup_slot_capacity_reserved_defaults_zero() -> None:
    from decimal import Decimal

    assert PickupSlot.__table__.c.capacity_reserved.default.arg == Decimal("0")


def test_pickup_slot_unique_per_area_date_and_times() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in PickupSlot.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("service_area_id", "slot_date", "start_time", "end_time") in unique_columns


def test_slot_foreign_keys_cascade_on_delete() -> None:
    for model in (PickupSlot, DeliverySlot):
        for constraint in model.__table__.constraints:
            if isinstance(constraint, ForeignKeyConstraint):
                for fk in constraint.elements:
                    assert fk.ondelete == "CASCADE"


def test_reservation_status_defaults_active() -> None:
    assert PickupSlotReservation.__table__.c.status.default.arg is ReservationStatus.ACTIVE


def test_reservation_has_no_partner_or_order_column() -> None:
    # Deliberate design decision -- see the model's docstring: a
    # reservation is against the slot's capacity, not a specific
    # partner (assignment is Phase 9) or order (Order doesn't exist
    # until Phase 8).
    columns = set(PickupSlotReservation.__table__.c.keys())
    assert "partner_profile_id" not in columns
    assert "order_id" not in columns
