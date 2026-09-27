"""Persistence for :class:`core.models.pricing_rule.PricingRule`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.pricing_rule import PricingRule


class PricingRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_service(self, service_id: uuid.UUID) -> PricingRule | None:
        stmt = select(PricingRule).where(
            PricingRule.service_id == service_id, PricingRule.effective_to.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, pricing_rule: PricingRule) -> PricingRule:
        self._session.add(pricing_rule)
        await self._session.flush()
        return pricing_rule

    async def update(self, pricing_rule: PricingRule) -> PricingRule:
        await self._session.flush()
        return pricing_rule
