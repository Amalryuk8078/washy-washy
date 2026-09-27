"""Offline (no database) tests for the Phase 9 partner-operations model
definitions: PartnerFacility, the Order/OrderItem assignment/inspection
additions, and OrderAssignmentHistory.
"""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from core.models import AssignmentRole, Order, OrderAssignmentHistory, OrderItem, PartnerFacility


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_assignment_role_matches_spec() -> None:
    assert {r.value for r in AssignmentRole} == {
        "FACILITY",
        "PICKUP_OPERATOR",
        "DELIVERY_OPERATOR",
    }


def test_partner_facility_unique_per_partner_and_name() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in PartnerFacility.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("partner_profile_id", "name") in unique_columns


def test_partner_facility_defaults_active() -> None:
    assert PartnerFacility.__table__.c.is_active.default.arg is True


def test_partner_facility_fk_ondelete() -> None:
    ondelete_by_column = {}
    for constraint in PartnerFacility.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                ondelete_by_column[fk.parent.name] = fk.ondelete

    # Owned by the partner -- cascades with it.
    assert ondelete_by_column["partner_profile_id"] == "CASCADE"
    # A reference to an independent resource -- does not cascade.
    assert ondelete_by_column["service_area_id"] is None


def test_order_assignment_columns_are_nullable() -> None:
    for column in (
        "assigned_facility_id",
        "pickup_operator_user_id",
        "delivery_operator_user_id",
    ):
        assert Order.__table__.c[column].nullable is True


def test_order_assignment_fk_ondelete() -> None:
    ondelete_by_column = {}
    for constraint in Order.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                ondelete_by_column[fk.parent.name] = fk.ondelete

    # A reference to an independent resource (a facility) -- no cascade.
    assert ondelete_by_column["assigned_facility_id"] is None
    # Operator assignments clear on the operator's account being
    # deleted, rather than blocking the deletion or cascading the order.
    assert ondelete_by_column["pickup_operator_user_id"] == "SET NULL"
    assert ondelete_by_column["delivery_operator_user_id"] == "SET NULL"


def test_order_item_inspection_columns() -> None:
    assert OrderItem.__table__.c.condition_notes.nullable is True
    assert OrderItem.__table__.c.damage_reported.default.arg is False


def test_order_assignment_history_has_no_updated_at() -> None:
    columns = set(OrderAssignmentHistory.__table__.c.keys())
    assert "created_at" in columns
    assert "updated_at" not in columns


def test_order_assignment_history_fk_ondelete() -> None:
    ondelete_by_column = {}
    for constraint in OrderAssignmentHistory.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                ondelete_by_column[fk.parent.name] = fk.ondelete

    assert ondelete_by_column["order_id"] == "CASCADE"
    assert ondelete_by_column["changed_by_user_id"] == "SET NULL"


def test_order_assignment_history_assignee_columns_are_not_foreign_keys() -> None:
    # Deliberate design decision -- see the model's docstring: which
    # table an assignee id points into depends on assignment_role
    # (a PartnerFacility for FACILITY, a User for either operator role),
    # so these are plain audit columns, not real foreign keys.
    fk_columns = set()
    for constraint in OrderAssignmentHistory.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                fk_columns.add(fk.parent.name)

    assert "previous_assignee_id" not in fk_columns
    assert "new_assignee_id" not in fk_columns
