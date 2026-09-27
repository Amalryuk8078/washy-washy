"""Pricing business logic: versioned per-service/material rates and the
price-breakdown calculation built from them.

Backend-authoritative: nothing here trusts a client-supplied price.
Deliberately independent of orders (Phase 8) — this only knows how to
compute a price from inputs; persisting a computed breakdown onto an
order (so a later rate change can't alter an existing order's total) is
Phase 8's job once ``Order``/``OrderItem`` exist. The *same*
``calculate_price`` call serves both an "estimated" price (customer-
declared material/quantity, before pickup) and a "final" price
(facility-verified material/quantity, after inspection) — the formula
never changes, only which inputs the caller passes in.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.material_pricing_rule import MaterialPricingRule
from core.models.pricing_rule import PricingModel, PricingRule
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.material_pricing_rule_repo import MaterialPricingRuleRepository
from washy_washy.repositories.material_repo import MaterialRepository
from washy_washy.repositories.pricing_rule_repo import PricingRuleRepository
from washy_washy.repositories.service_material_repo import ServiceMaterialRepository
from washy_washy.repositories.service_repo import ServiceRepository

ZERO = Decimal("0")

# Which of quantity/weight_kg each pricing model needs, so a mismatched
# input is caught with a clear error instead of a silent Decimal("0").
_QUANTITY_MODELS = (PricingModel.PER_ITEM, PricingModel.PER_BAG)
_WEIGHT_MODELS = (PricingModel.PER_KG, PricingModel.BASE_PLUS_WEIGHT)


@dataclass(frozen=True)
class PriceBreakdown:
    """Every component of the formula, never just the total — a caller
    (and eventually an invoice, Phase 10) needs to show where a price
    came from, not just what it is.
    """

    base: Decimal
    material_adjustment: Decimal
    care_adjustment: Decimal
    quantity_charge: Decimal
    rush_charge: Decimal
    delivery_charge: Decimal
    tax: Decimal
    discount: Decimal
    subtotal: Decimal
    total: Decimal
    pricing_rule_id: uuid.UUID
    material_pricing_rule_id: uuid.UUID | None


class PricingService:
    def __init__(self, session: AsyncSession) -> None:
        self._pricing_rules = PricingRuleRepository(session)
        self._material_pricing_rules = MaterialPricingRuleRepository(session)
        self._service_materials = ServiceMaterialRepository(session)
        self._services = ServiceRepository(session)
        self._materials = MaterialRepository(session)

    # -- Versioned rates --------------------------------------------------

    async def set_service_pricing(
        self,
        service_id: uuid.UUID,
        pricing_model: str,
        base_price: Decimal,
        unit_price: Decimal,
    ) -> PricingRule:
        """Closes the service's current active rule (if any) and opens a
        new one. Two separate flushes, not one — close the old row and
        flush *before* inserting the new one — so the two rows are never
        simultaneously "active" mid-flush, which the partial unique
        index would reject even within the same transaction (same
        pattern as ``AddressService.set_default_address``).
        """
        if await self._services.get_by_id(service_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

        now = datetime.now(UTC)
        current = await self._pricing_rules.get_active_for_service(service_id)
        if current is not None:
            current.effective_to = now
            await self._pricing_rules.update(current)

        new_rule = PricingRule(
            service_id=service_id,
            pricing_model=pricing_model,
            base_price=base_price,
            unit_price=unit_price,
            effective_from=now,
        )
        return await self._pricing_rules.create(new_rule)

    async def set_material_pricing(
        self, material_id: uuid.UUID, price_adjustment: Decimal
    ) -> MaterialPricingRule:
        if await self._materials.get_by_id(material_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

        now = datetime.now(UTC)
        current = await self._material_pricing_rules.get_active_for_material(material_id)
        if current is not None:
            current.effective_to = now
            await self._material_pricing_rules.update(current)

        new_rule = MaterialPricingRule(
            material_id=material_id, price_adjustment=price_adjustment, effective_from=now
        )
        return await self._material_pricing_rules.create(new_rule)

    async def get_active_service_pricing(self, service_id: uuid.UUID) -> PricingRule:
        rule = await self._pricing_rules.get_active_for_service(service_id)
        if rule is None:
            raise NotFoundException(
                error_messages.NO_ACTIVE_PRICING_RULE, error_codes.NO_ACTIVE_PRICING_RULE
            )
        return rule

    async def get_active_material_pricing(
        self, material_id: uuid.UUID
    ) -> MaterialPricingRule | None:
        return await self._material_pricing_rules.get_active_for_material(material_id)

    # -- Calculation -------------------------------------------------------

    async def calculate_price(
        self,
        *,
        service_id: uuid.UUID,
        material_id: uuid.UUID,
        quantity: int | None = None,
        weight_kg: Decimal | None = None,
        custom_charge: Decimal | None = None,
        rush_charge: Decimal = ZERO,
        delivery_charge: Decimal = ZERO,
        tax: Decimal = ZERO,
        discount: Decimal = ZERO,
    ) -> PriceBreakdown:
        pricing_rule = await self.get_active_service_pricing(service_id)

        material_rule = await self._material_pricing_rules.get_active_for_material(material_id)
        material_adjustment = material_rule.price_adjustment if material_rule is not None else ZERO

        service_material = await self._service_materials.get(service_id, material_id)
        care_adjustment = ZERO
        if service_material is not None and service_material.care_adjustment is not None:
            care_adjustment = service_material.care_adjustment

        quantity_charge = self._compute_quantity_charge(
            pricing_rule, quantity=quantity, weight_kg=weight_kg, custom_charge=custom_charge
        )

        subtotal = pricing_rule.base_price + material_adjustment + care_adjustment + quantity_charge
        total = subtotal + rush_charge + delivery_charge + tax - discount

        return PriceBreakdown(
            base=pricing_rule.base_price,
            material_adjustment=material_adjustment,
            care_adjustment=care_adjustment,
            quantity_charge=quantity_charge,
            rush_charge=rush_charge,
            delivery_charge=delivery_charge,
            tax=tax,
            discount=discount,
            subtotal=subtotal,
            total=total,
            pricing_rule_id=pricing_rule.id,
            material_pricing_rule_id=material_rule.id if material_rule is not None else None,
        )

    @staticmethod
    def _compute_quantity_charge(
        pricing_rule: PricingRule,
        *,
        quantity: int | None,
        weight_kg: Decimal | None,
        custom_charge: Decimal | None,
    ) -> Decimal:
        model = pricing_rule.pricing_model

        if model in _QUANTITY_MODELS:
            if quantity is None:
                raise BusinessRuleException(
                    error_messages.QUANTITY_REQUIRED, error_codes.QUANTITY_REQUIRED
                )
            return pricing_rule.unit_price * quantity

        if model in _WEIGHT_MODELS:
            if weight_kg is None:
                raise BusinessRuleException(
                    error_messages.WEIGHT_REQUIRED, error_codes.WEIGHT_REQUIRED
                )
            return pricing_rule.unit_price * weight_kg

        if model == PricingModel.CUSTOM:
            return custom_charge if custom_charge is not None else ZERO

        raise BusinessRuleException(
            error_messages.UNKNOWN_PRICING_MODEL, error_codes.UNKNOWN_PRICING_MODEL
        )
