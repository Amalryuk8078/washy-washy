"""Persistence for :class:`core.models.service.Service`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.service import Service


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, service_id: uuid.UUID) -> Service | None:
        return await self._session.get(Service, service_id)

    async def get_by_name(self, name: str) -> Service | None:
        stmt = select(Service).where(Service.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, *, include_inactive: bool = False) -> list[Service]:
        stmt = select(Service).order_by(Service.name)
        if not include_inactive:
            stmt = stmt.where(Service.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, service: Service) -> Service:
        self._session.add(service)
        await self._session.flush()
        return service

    async def update(self, service: Service) -> Service:
        await self._session.flush()
        return service
