"""Offline (no database) tests for the Phase 1 RBAC model definitions:
column shapes, constraints, and the enums documenting the designed
resource/action/scope semantics.

These only inspect Python-side table metadata — they do not prove
PostgreSQL actually *enforces* uniqueness/FK/CHECK constraints. That
requires a live database; see tests/integration/test_user_identity.py
and tests/integration/test_rbac_associations.py for those.
"""

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from core.models import (
    Base,
    Permission,
    Role,
    RoleName,
    RolePermission,
    User,
    UserRole,
)
from washy_washy.repositories.user_repo import normalize_email


def _unique_constraint_column_sets(table) -> set[tuple[str, ...]]:
    return {
        tuple(c.name for c in con.columns)
        for con in table.constraints
        if isinstance(con, UniqueConstraint)
    }


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_all_five_tables_registered_on_metadata() -> None:
    # Subset, not exact equality: Base.metadata is a shared, process-wide
    # object, and other test modules (e.g. test_database_foundation.py)
    # register their own throwaway tables on it too.
    expected = {"users", "roles", "permissions", "user_roles", "role_permissions"}
    assert expected.issubset(Base.metadata.tables)


def test_user_has_no_role_column() -> None:
    # Roles are assigned via UserRole so a user can hold more than one.
    assert "role" not in User.__table__.c
    assert "role_id" not in User.__table__.c


@pytest.mark.parametrize(
    ("column", "nullable"),
    [
        ("email", False),
        ("phone", True),
        ("password_hash", False),
        ("first_name", False),
        ("last_name", True),
        ("is_active", False),
        ("is_verified", False),
    ],
)
def test_user_column_nullability(column: str, nullable: bool) -> None:
    assert User.__table__.c[column].nullable is nullable


def test_user_email_and_phone_are_unique() -> None:
    unique_columns = _unique_constraint_column_sets(User.__table__)
    assert ("email",) in unique_columns
    assert ("phone",) in unique_columns


def test_user_stores_password_hash_only() -> None:
    column_names = set(User.__table__.c.keys())
    assert "password_hash" in column_names
    assert not {"password", "plain_password", "raw_password"} & column_names


def test_user_is_active_defaults_true() -> None:
    assert User.__table__.c.is_active.default.arg is True


def test_user_is_verified_defaults_false() -> None:
    assert User.__table__.c.is_verified.default.arg is False


def test_role_name_is_unique() -> None:
    assert ("name",) in _unique_constraint_column_sets(Role.__table__)


def test_role_is_active_defaults_true() -> None:
    assert Role.__table__.c.is_active.default.arg is True


def test_role_name_enum_matches_foundational_roles() -> None:
    assert {member.value for member in RoleName} == {
        "CUSTOMER",
        "LAUNDRY_PARTNER",
        "SUPERVISOR",
        "ADMIN",
    }


def test_permission_uniqueness_is_resource_action_scope() -> None:
    assert ("resource", "action", "scope") in _unique_constraint_column_sets(Permission.__table__)


def test_permission_scope_is_never_nullable() -> None:
    # scope must always be populated -- a NULL-able scope would let
    # PostgreSQL silently accept duplicate (resource, action, NULL) rows,
    # since NULLs never compare equal under a standard UNIQUE constraint.
    assert Permission.__table__.c.scope.nullable is False


def test_permission_has_scope_check_constraint() -> None:
    check_constraints = [
        con for con in Permission.__table__.constraints if isinstance(con, CheckConstraint)
    ]
    assert any("scope" in str(con.sqltext) for con in check_constraints)


def test_user_role_uniqueness_is_user_and_role() -> None:
    assert ("user_id", "role_id") in _unique_constraint_column_sets(UserRole.__table__)


def test_user_role_has_no_updated_at() -> None:
    # Association rows are immutable: created or removed, never edited.
    assert "updated_at" not in UserRole.__table__.c.keys()
    assert "created_at" in UserRole.__table__.c.keys()


def test_user_role_foreign_keys_cascade_on_delete() -> None:
    for constraint in UserRole.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"


def test_role_permission_uniqueness_is_role_and_permission() -> None:
    assert ("role_id", "permission_id") in _unique_constraint_column_sets(RolePermission.__table__)


def test_role_permission_has_no_updated_at() -> None:
    assert "updated_at" not in RolePermission.__table__.c.keys()
    assert "created_at" in RolePermission.__table__.c.keys()


def test_role_permission_foreign_keys_cascade_on_delete() -> None:
    for constraint in RolePermission.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Amal@Example.COM", "amal@example.com"),
        ("  spaced@example.com  ", "spaced@example.com"),
        ("already@lower.com", "already@lower.com"),
    ],
)
def test_normalize_email(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected
