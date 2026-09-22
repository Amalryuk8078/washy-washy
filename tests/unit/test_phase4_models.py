"""Offline (no database) tests for the Phase 4 model definitions:
CustomerProfile, PartnerProfile, Address, ServiceArea,
ServiceAreaPostalCode.
"""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from core.models import (
    Address,
    CustomerProfile,
    PartnerProfile,
    PartnerStatus,
    ServiceArea,
    ServiceAreaPostalCode,
)


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_customer_profile_user_id_is_unique() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in CustomerProfile.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("user_id",) in unique_columns


def test_customer_profile_has_no_auth_fields() -> None:
    column_names = set(CustomerProfile.__table__.c.keys())
    assert not {"email", "password", "password_hash", "is_active"} & column_names


def test_partner_profile_user_id_is_unique() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in PartnerProfile.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("user_id",) in unique_columns


def test_partner_profile_status_defaults_to_pending() -> None:
    assert PartnerProfile.__table__.c.status.default.arg is PartnerStatus.PENDING


def test_partner_profile_has_no_auth_fields() -> None:
    column_names = set(PartnerProfile.__table__.c.keys())
    assert not {"email", "password", "password_hash", "is_active"} & column_names


def test_address_foreign_key_cascades_on_delete() -> None:
    for constraint in Address.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"


def test_address_is_default_defaults_false() -> None:
    assert Address.__table__.c.is_default.default.arg is False


def test_address_has_partial_unique_default_index() -> None:
    partial_unique_indexes = [
        ix
        for ix in Address.__table__.indexes
        if ix.unique and ix.dialect_options["postgresql"]["where"] is not None
    ]
    assert len(partial_unique_indexes) == 1
    index = partial_unique_indexes[0]
    assert [c.name for c in index.columns] == ["user_id"]


def test_address_has_plain_index_on_user_id() -> None:
    plain_indexes = [ix for ix in Address.__table__.indexes if not ix.unique]
    assert any([c.name for c in ix.columns] == ["user_id"] for ix in plain_indexes)


def test_service_area_name_is_unique() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in ServiceArea.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("name",) in unique_columns


def test_service_area_is_active_defaults_true() -> None:
    assert ServiceArea.__table__.c.is_active.default.arg is True


def test_service_area_postal_code_is_globally_unique() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in ServiceAreaPostalCode.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("postal_code",) in unique_columns


def test_service_area_postal_code_cascades_on_delete() -> None:
    for constraint in ServiceAreaPostalCode.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"


def test_service_area_postal_code_has_no_updated_at() -> None:
    assert "updated_at" not in ServiceAreaPostalCode.__table__.c.keys()
    assert "created_at" in ServiceAreaPostalCode.__table__.c.keys()


def test_no_direct_user_service_area_relationship_table() -> None:
    # Deliberate design decision (see core/models/service_area.py and
    # FLOW.md's Phase 4 section): serviceability is a property of a
    # location (a postal code), not of a user, so there is no
    # user_service_areas-style association table.
    from core.models import Base

    assert "user_service_areas" not in Base.metadata.tables
