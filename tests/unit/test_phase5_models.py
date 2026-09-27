"""Offline (no database) tests for the Phase 5 catalog model definitions:
Service, Material, ServiceMaterial, PartnerCapability.
"""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from core.models import Material, PartnerCapability, Service, ServiceMaterial


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_service_name_is_unique() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in Service.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("name",) in unique_columns


def test_service_is_active_defaults_true() -> None:
    assert Service.__table__.c.is_active.default.arg is True


def test_material_name_is_unique() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in Material.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("name",) in unique_columns


def test_material_is_active_defaults_true() -> None:
    assert Material.__table__.c.is_active.default.arg is True


def test_service_material_uniqueness_is_service_and_material() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in ServiceMaterial.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("service_id", "material_id") in unique_columns


def test_service_material_has_updated_at() -> None:
    # Unlike the pure yes/no association tables (UserRole,
    # PartnerCapability), ServiceMaterial carries editable content (care
    # instructions, temperature), so it uses TimestampMixin.
    assert "updated_at" in ServiceMaterial.__table__.c.keys()


def test_service_material_foreign_keys_cascade_on_delete() -> None:
    for constraint in ServiceMaterial.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"


def test_partner_capability_uniqueness_is_partner_and_service() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in PartnerCapability.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("partner_profile_id", "service_id") in unique_columns


def test_partner_capability_has_no_updated_at() -> None:
    assert "updated_at" not in PartnerCapability.__table__.c.keys()
    assert "created_at" in PartnerCapability.__table__.c.keys()


def test_partner_capability_foreign_keys_cascade_on_delete() -> None:
    for constraint in PartnerCapability.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"
