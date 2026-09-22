"""Persistence for :class:`core.models.service_area.ServiceArea` and
:class:`core.models.service_area_postal_code.ServiceAreaPostalCode`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.service_area import ServiceArea
from core.models.service_area_postal_code import ServiceAreaPostalCode


class ServiceAreaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, service_area_id: uuid.UUID) -> ServiceArea | None:
        return await self._session.get(ServiceArea, service_area_id)

    async def get_by_name(self, name: str) -> ServiceArea | None:
        stmt = select(ServiceArea).where(ServiceArea.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[ServiceArea]:
        stmt = select(ServiceArea).where(ServiceArea.is_active.is_(True)).order_by(ServiceArea.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, service_area: ServiceArea) -> ServiceArea:
        self._session.add(service_area)
        await self._session.flush()
        return service_area

    async def get_by_postal_code(self, postal_code: str) -> ServiceArea | None:
        """The area (if any, and only if active) covering this postal
        code — the query behind "is this address serviceable?".
        """
        stmt = (
            select(ServiceArea)
            .join(ServiceAreaPostalCode, ServiceAreaPostalCode.service_area_id == ServiceArea.id)
            .where(
                ServiceAreaPostalCode.postal_code == postal_code,
                ServiceArea.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_postal_code(
        self, service_area_id: uuid.UUID, postal_code: str
    ) -> ServiceAreaPostalCode:
        """Does not pre-check for an existing mapping: the database's
        unique constraint on ``postal_code`` is the real guard against
        mapping the same code to two areas under concurrent requests.
        """
        mapping = ServiceAreaPostalCode(service_area_id=service_area_id, postal_code=postal_code)
        self._session.add(mapping)
        await self._session.flush()
        return mapping
