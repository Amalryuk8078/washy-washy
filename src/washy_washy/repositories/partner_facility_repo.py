"""Persistence for :class:`core.models.partner_facility.PartnerFacility`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.partner_facility import PartnerFacility


class PartnerFacilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, facility_id: uuid.UUID) -> PartnerFacility | None:
        return await self._session.get(PartnerFacility, facility_id)

    async def get_by_name(self, partner_profile_id: uuid.UUID, name: str) -> PartnerFacility | None:
        stmt = select(PartnerFacility).where(
            PartnerFacility.partner_profile_id == partner_profile_id,
            PartnerFacility.name == name,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_partner(
        self, partner_profile_id: uuid.UUID, *, active_only: bool = True
    ) -> list[PartnerFacility]:
        stmt = select(PartnerFacility).where(
            PartnerFacility.partner_profile_id == partner_profile_id
        )
        if active_only:
            stmt = stmt.where(PartnerFacility.is_active.is_(True))
        stmt = stmt.order_by(PartnerFacility.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self, *, active_only: bool = True) -> list[PartnerFacility]:
        stmt = select(PartnerFacility)
        if active_only:
            stmt = stmt.where(PartnerFacility.is_active.is_(True))
        stmt = stmt.order_by(PartnerFacility.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, facility: PartnerFacility) -> PartnerFacility:
        self._session.add(facility)
        await self._session.flush()
        return facility

    async def update(self, facility: PartnerFacility) -> PartnerFacility:
        await self._session.flush()
        return facility
