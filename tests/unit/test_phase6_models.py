"""Offline (no database) tests for the Phase 6 pricing model definitions:
PricingRule, MaterialPricingRule, and ServiceMaterial's new
care_adjustment column.
"""

from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.orm import configure_mappers

from core.models import MaterialPricingRule, PricingModel, PricingRule, ServiceMaterial


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_pricing_model_enum_matches_spec() -> None:
    assert {member.value for member in PricingModel} == {
        "PER_ITEM",
        "PER_KG",
        "PER_BAG",
        "BASE_PLUS_WEIGHT",
        "CUSTOM",
    }


def test_pricing_rule_effective_to_nullable() -> None:
    assert PricingRule.__table__.c.effective_to.nullable is True


def test_pricing_rule_has_one_active_per_service_partial_index() -> None:
    partial_unique_indexes = [
        ix
        for ix in PricingRule.__table__.indexes
        if ix.unique and ix.dialect_options["postgresql"]["where"] is not None
    ]
    assert len(partial_unique_indexes) == 1
    assert [c.name for c in partial_unique_indexes[0].columns] == ["service_id"]


def test_pricing_rule_foreign_key_cascades_on_delete() -> None:
    for constraint in PricingRule.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"


def test_material_pricing_rule_has_one_active_per_material_partial_index() -> None:
    partial_unique_indexes = [
        ix
        for ix in MaterialPricingRule.__table__.indexes
        if ix.unique and ix.dialect_options["postgresql"]["where"] is not None
    ]
    assert len(partial_unique_indexes) == 1
    assert [c.name for c in partial_unique_indexes[0].columns] == ["material_id"]


def test_service_material_has_care_adjustment_column() -> None:
    assert "care_adjustment" in ServiceMaterial.__table__.c.keys()
    assert ServiceMaterial.__table__.c.care_adjustment.nullable is True
