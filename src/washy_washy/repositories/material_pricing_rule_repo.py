"""Persistence for :class:`core.models.material_pricing_rule.MaterialPricingRule`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.material_pricing_rule import MaterialPricingRule


class MaterialPricingRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_material(self, material_id: uuid.UUID) -> MaterialPricingRule | None:
        stmt = select(MaterialPricingRule).where(
            MaterialPricingRule.material_id == material_id,
            MaterialPricingRule.effective_to.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, rule: MaterialPricingRule) -> MaterialPricingRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update(self, rule: MaterialPricingRule) -> MaterialPricingRule:
        await self._session.flush()
        return rule
