"""Integration tests for PricingService — versioned rates and the price
breakdown calculation — against a real PostgreSQL database.
"""

import uuid
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.pricing_rule import PricingModel
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.pricing_service import PricingService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


async def _make_service(db_session):
    return await CatalogService(db_session).create_service(_unique("Wash"))


async def _make_material(db_session):
    return await CatalogService(db_session).create_material(_unique("Cotton"))


@pytest.mark.asyncio
async def test_set_and_get_service_pricing(db_session) -> None:
    service = await _make_service(db_session)
    pricing = PricingService(db_session)

    rule = await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.50")
    )

    assert rule.effective_to is None
    fetched = await pricing.get_active_service_pricing(service.id)
    assert fetched.id == rule.id


@pytest.mark.asyncio
async def test_service_with_no_pricing_rule_raises_not_found(db_session) -> None:
    service = await _make_service(db_session)

    with pytest.raises(NotFoundException):
        await PricingService(db_session).get_active_service_pricing(service.id)


@pytest.mark.asyncio
async def test_setting_new_price_closes_previous_version(db_session) -> None:
    service = await _make_service(db_session)
    pricing = PricingService(db_session)
    first = await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.50")
    )

    second = await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("3.00"), Decimal("2.00")
    )

    assert second.effective_to is None
    assert first.effective_to is not None
    # Historical immutability: the old row's own rate never changed.
    assert first.base_price == Decimal("2.00")
    assert first.unit_price == Decimal("1.50")
    active = await pricing.get_active_service_pricing(service.id)
    assert active.id == second.id


@pytest.mark.asyncio
async def test_set_material_pricing_and_versioning(db_session) -> None:
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    first = await pricing.set_material_pricing(material.id, Decimal("1.00"))

    second = await pricing.set_material_pricing(material.id, Decimal("1.50"))

    assert first.effective_to is not None
    assert first.price_adjustment == Decimal("1.00")
    active = await pricing.get_active_material_pricing(material.id)
    assert active.id == second.id
    assert active.price_adjustment == Decimal("1.50")


@pytest.mark.asyncio
async def test_calculate_price_per_item(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.50")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, quantity=4
    )

    assert breakdown.base == Decimal("2.00")
    assert breakdown.quantity_charge == Decimal("6.00")  # 1.50 * 4
    assert breakdown.material_adjustment == Decimal("0")
    assert breakdown.care_adjustment == Decimal("0")
    assert breakdown.subtotal == Decimal("8.00")
    assert breakdown.total == Decimal("8.00")


@pytest.mark.asyncio
async def test_calculate_price_per_item_requires_quantity(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.50")
    )

    with pytest.raises(BusinessRuleException):
        await pricing.calculate_price(service_id=service.id, material_id=material.id)


@pytest.mark.asyncio
async def test_calculate_price_per_kg(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_KG.value, Decimal("1.00"), Decimal("3.00")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, weight_kg=Decimal("2.5")
    )

    assert breakdown.quantity_charge == Decimal("7.50")  # 3.00 * 2.5


@pytest.mark.asyncio
async def test_calculate_price_per_kg_requires_weight(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_KG.value, Decimal("1.00"), Decimal("3.00")
    )

    with pytest.raises(BusinessRuleException):
        await pricing.calculate_price(service_id=service.id, material_id=material.id, quantity=2)


@pytest.mark.asyncio
async def test_calculate_price_per_bag(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_BAG.value, Decimal("0"), Decimal("15.00")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, quantity=2
    )

    assert breakdown.quantity_charge == Decimal("30.00")


@pytest.mark.asyncio
async def test_calculate_price_base_plus_weight(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.BASE_PLUS_WEIGHT.value, Decimal("5.00"), Decimal("2.00")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, weight_kg=Decimal("3")
    )

    assert breakdown.base == Decimal("5.00")
    assert breakdown.quantity_charge == Decimal("6.00")
    assert breakdown.subtotal == Decimal("11.00")


@pytest.mark.asyncio
async def test_calculate_price_custom_uses_custom_charge(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.CUSTOM.value, Decimal("0"), Decimal("0")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, custom_charge=Decimal("42.00")
    )

    assert breakdown.quantity_charge == Decimal("42.00")


@pytest.mark.asyncio
async def test_calculate_price_custom_without_charge_defaults_to_zero(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.CUSTOM.value, Decimal("10.00"), Decimal("0")
    )

    breakdown = await pricing.calculate_price(service_id=service.id, material_id=material.id)

    assert breakdown.quantity_charge == Decimal("0")
    assert breakdown.subtotal == Decimal("10.00")


@pytest.mark.asyncio
async def test_calculate_price_includes_material_adjustment(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.00")
    )
    await pricing.set_material_pricing(material.id, Decimal("3.00"))

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, quantity=1
    )

    assert breakdown.material_adjustment == Decimal("3.00")
    assert breakdown.subtotal == Decimal("6.00")  # 2 + 3 + 1


@pytest.mark.asyncio
async def test_calculate_price_includes_care_adjustment(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    catalog = CatalogService(db_session)
    await catalog.set_compatibility(service.id, material.id, care_adjustment=Decimal("4.00"))
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.00")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, quantity=1
    )

    assert breakdown.care_adjustment == Decimal("4.00")
    assert breakdown.subtotal == Decimal("7.00")  # 2 + 4 + 1


@pytest.mark.asyncio
async def test_calculate_price_applies_rush_delivery_tax_discount(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("10.00"), Decimal("0")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id,
        material_id=material.id,
        quantity=1,
        rush_charge=Decimal("5.00"),
        delivery_charge=Decimal("2.50"),
        tax=Decimal("1.00"),
        discount=Decimal("3.00"),
    )

    assert breakdown.subtotal == Decimal("10.00")
    # 10 + 5 + 2.5 + 1 - 3
    assert breakdown.total == Decimal("15.50")


@pytest.mark.asyncio
async def test_calculate_price_is_decimal_precise_not_float(db_session) -> None:
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("0.10"), Decimal("0.20")
    )

    breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, quantity=3
    )

    assert isinstance(breakdown.total, Decimal)
    # 0.10 + 0.20*3 = 0.70 exactly -- a float would risk 0.6999999999999998.
    assert breakdown.total == Decimal("0.70")


@pytest.mark.asyncio
async def test_estimated_and_final_price_use_same_calculation(db_session) -> None:
    """No separate 'estimate' vs 'final' method -- Phase 8's order flow
    calls calculate_price twice with different inputs (declared vs.
    verified material/quantity); the formula itself never changes.
    """
    service = await _make_service(db_session)
    declared_material = await _make_material(db_session)
    verified_material = await _make_material(db_session)
    pricing = PricingService(db_session)
    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.00")
    )
    await pricing.set_material_pricing(verified_material.id, Decimal("5.00"))

    estimated = await pricing.calculate_price(
        service_id=service.id, material_id=declared_material.id, quantity=2
    )
    final = await pricing.calculate_price(
        service_id=service.id, material_id=verified_material.id, quantity=3
    )

    assert estimated.total == Decimal("4.00")  # 2 + 0 + 1*2
    assert final.total == Decimal("10.00")  # 2 + 5 + 1*3


@pytest.mark.asyncio
async def test_price_computed_under_old_rule_version_is_unaffected_by_later_change(
    db_session,
) -> None:
    """Historical immutability: a breakdown computed while a rule was
    active keeps referencing that exact rule id even after a newer
    version supersedes it.
    """
    service = await _make_service(db_session)
    material = await _make_material(db_session)
    pricing = PricingService(db_session)
    old_rule = await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("2.00"), Decimal("1.00")
    )

    old_breakdown = await pricing.calculate_price(
        service_id=service.id, material_id=material.id, quantity=1
    )
    assert old_breakdown.pricing_rule_id == old_rule.id

    await pricing.set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("99.00"), Decimal("50.00")
    )

    # The old rule row itself never changed, regardless of the new one.
    assert old_rule.base_price == Decimal("2.00")
    assert old_breakdown.total == Decimal("3.00")
