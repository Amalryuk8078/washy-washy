"""Persistence for :class:`core.models.operating_hours.OperatingHours`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.operating_hours import OperatingHours


class OperatingHoursRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, service_area_id: uuid.UUID, day_of_week: str) -> OperatingHours | None:
        stmt = select(OperatingHours).where(
            OperatingHours.service_area_id == service_area_id,
            OperatingHours.day_of_week == day_of_week,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_service_area(self, service_area_id: uuid.UUID) -> list[OperatingHours]:
        stmt = select(OperatingHours).where(OperatingHours.service_area_id == service_area_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, hours: OperatingHours) -> OperatingHours:
        self._session.add(hours)
        await self._session.flush()
        return hours

    async def update(self, hours: OperatingHours) -> OperatingHours:
        await self._session.flush()
        return hours
