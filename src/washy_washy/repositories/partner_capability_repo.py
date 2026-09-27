"""Persistence for :class:`core.models.partner_capability.PartnerCapability`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.partner_capability import PartnerCapability
from core.models.service import Service


class PartnerCapabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_any_capability_for_service(self, service_id: uuid.UUID) -> bool:
        stmt = select(PartnerCapability.id).where(PartnerCapability.service_id == service_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def has_capability(self, partner_profile_id: uuid.UUID, service_id: uuid.UUID) -> bool:
        stmt = select(PartnerCapability.id).where(
            PartnerCapability.partner_profile_id == partner_profile_id,
            PartnerCapability.service_id == service_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_services_for_partner(self, partner_profile_id: uuid.UUID) -> list[Service]:
        stmt = (
            select(Service)
            .join(PartnerCapability, PartnerCapability.service_id == Service.id)
            .where(PartnerCapability.partner_profile_id == partner_profile_id)
            .order_by(Service.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def grant(
        self, partner_profile_id: uuid.UUID, service_id: uuid.UUID
    ) -> PartnerCapability:
        """Does not pre-check for an existing grant: the database's
        unique ``(partner_profile_id, service_id)`` constraint is the
        real guard against a duplicate under concurrent requests.
        """
        capability = PartnerCapability(partner_profile_id=partner_profile_id, service_id=service_id)
        self._session.add(capability)
        await self._session.flush()
        return capability

    async def revoke(self, partner_profile_id: uuid.UUID, service_id: uuid.UUID) -> None:
        stmt = select(PartnerCapability).where(
            PartnerCapability.partner_profile_id == partner_profile_id,
            PartnerCapability.service_id == service_id,
        )
        result = await self._session.execute(stmt)
        capability = result.scalar_one_or_none()
        if capability is not None:
            await self._session.delete(capability)
            await self._session.flush()
