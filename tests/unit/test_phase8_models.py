"""Offline (no database) tests for the Phase 8 order model definitions
and the order state machine's transition graph.
"""

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKeyConstraint
from sqlalchemy.orm import configure_mappers

from core.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from washy_washy.services.order_state_service import ALLOWED_TRANSITIONS


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_order_status_matches_spec() -> None:
    assert {s.value for s in OrderStatus} == {
        "DRAFT",
        "PENDING_PAYMENT",
        "CONFIRMED",
        "PICKUP_SCHEDULED",
        "PICKUP_ASSIGNED",
        "PICKUP_IN_PROGRESS",
        "PICKED_UP",
        "RECEIVED_AT_FACILITY",
        "INSPECTION",
        "ITEMIZED",
        "PRICE_FINALIZED",
        "PROCESSING",
        "QUALITY_CHECK",
        "READY_FOR_DELIVERY",
        "DELIVERY_ASSIGNED",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
        "COMPLETED",
        "PAYMENT_FAILED",
        "PICKUP_FAILED",
        "DELIVERY_FAILED",
        "PRICE_ADJUSTMENT_REQUIRED",
        "RESCHEDULED",
        "CANCELLED",
    }


def test_order_status_defaults_draft() -> None:
    assert Order.__table__.c.status.default.arg == OrderStatus.DRAFT.value


def test_order_estimated_total_defaults_zero() -> None:
    assert Order.__table__.c.estimated_total.default.arg == Decimal("0")


def test_order_has_capacity_check_constraints() -> None:
    check_names = {
        con.name for con in Order.__table__.constraints if isinstance(con, CheckConstraint)
    }
    assert "ck_orders_estimated_total_non_negative" in check_names
    assert "ck_orders_final_total_non_negative" in check_names


def test_order_customer_id_cascades_but_references_do_not() -> None:
    """Deliberate split (see the model's docstring): ``customer_id`` is
    ownership (cascades with the user), everything else is a reference
    to an independent resource (no ``ondelete`` -- defaults to RESTRICT)
    so deleting an address/slot that an order still points at fails
    loudly instead of silently erasing the order.
    """
    ondelete_by_column = {}
    for constraint in Order.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                ondelete_by_column[fk.parent.name] = fk.ondelete

    assert ondelete_by_column["customer_id"] == "CASCADE"
    for column in (
        "service_area_id",
        "pickup_address_id",
        "delivery_address_id",
        "pickup_slot_id",
        "delivery_slot_id",
        "pickup_reservation_id",
        "delivery_reservation_id",
    ):
        assert ondelete_by_column[column] is None


def test_order_slot_and_reservation_columns_are_nullable() -> None:
    for column in (
        "pickup_slot_id",
        "delivery_slot_id",
        "pickup_reservation_id",
        "delivery_reservation_id",
    ):
        assert Order.__table__.c[column].nullable is True


def test_order_item_declared_material_required_verified_optional() -> None:
    assert OrderItem.__table__.c.declared_material_id.nullable is False
    assert OrderItem.__table__.c.verified_material_id.nullable is True


def test_order_item_has_line_total_check_constraints() -> None:
    check_names = {
        con.name for con in OrderItem.__table__.constraints if isinstance(con, CheckConstraint)
    }
    assert "ck_order_items_estimated_line_total_non_negative" in check_names
    assert "ck_order_items_final_line_total_non_negative" in check_names


def test_order_item_order_id_cascades_on_delete() -> None:
    for constraint in OrderItem.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                if fk.parent.name == "order_id":
                    assert fk.ondelete == "CASCADE"


def test_order_status_history_has_no_updated_at() -> None:
    columns = set(OrderStatusHistory.__table__.c.keys())
    assert "created_at" in columns
    assert "updated_at" not in columns


def test_order_status_history_changed_by_sets_null_on_delete() -> None:
    for constraint in OrderStatusHistory.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                if fk.parent.name == "changed_by_user_id":
                    assert fk.ondelete == "SET NULL"
                if fk.parent.name == "order_id":
                    assert fk.ondelete == "CASCADE"


def test_order_status_history_metadata_column_maps_to_extra_data() -> None:
    # The DB column is literally named "metadata" (per the Phase 8 spec's
    # field list); the Python attribute is "extra_data" to avoid
    # colliding with SQLAlchemy's own reserved Base.metadata.
    assert "extra_data" not in OrderStatusHistory.__table__.c.keys()
    assert "metadata" in OrderStatusHistory.__table__.c.keys()
    assert hasattr(OrderStatusHistory, "extra_data")


def test_completed_and_cancelled_are_terminal() -> None:
    assert ALLOWED_TRANSITIONS[OrderStatus.COMPLETED] == frozenset()
    assert ALLOWED_TRANSITIONS[OrderStatus.CANCELLED] == frozenset()


def test_completed_to_draft_is_not_allowed() -> None:
    # The spec's own explicit example of an illegal transition.
    assert OrderStatus.DRAFT not in ALLOWED_TRANSITIONS[OrderStatus.COMPLETED]


def test_draft_can_move_to_pending_payment_or_cancelled() -> None:
    assert ALLOWED_TRANSITIONS[OrderStatus.DRAFT] == frozenset(
        {OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED}
    )


def test_every_status_appears_in_the_transition_graph() -> None:
    assert set(ALLOWED_TRANSITIONS.keys()) == set(OrderStatus)
