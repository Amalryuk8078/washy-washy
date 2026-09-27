"""Persistence for :class:`core.models.partner_availability.PartnerAvailability`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.partner_availability import PartnerAvailability


class PartnerAvailabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, partner_profile_id: uuid.UUID, day_of_week: str
    ) -> PartnerAvailability | None:
        stmt = select(PartnerAvailability).where(
            PartnerAvailability.partner_profile_id == partner_profile_id,
            PartnerAvailability.day_of_week == day_of_week,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_partner(self, partner_profile_id: uuid.UUID) -> list[PartnerAvailability]:
        stmt = select(PartnerAvailability).where(
            PartnerAvailability.partner_profile_id == partner_profile_id
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, availability: PartnerAvailability) -> PartnerAvailability:
        self._session.add(availability)
        await self._session.flush()
        return availability

    async def update(self, availability: PartnerAvailability) -> PartnerAvailability:
        await self._session.flush()
        return availability
