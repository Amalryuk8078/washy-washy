"""Persistence for :class:`core.models.material.Material`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.material import Material


class MaterialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, material_id: uuid.UUID) -> Material | None:
        return await self._session.get(Material, material_id)

    async def get_by_name(self, name: str) -> Material | None:
        stmt = select(Material).where(Material.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, *, include_inactive: bool = False) -> list[Material]:
        stmt = select(Material).order_by(Material.name)
        if not include_inactive:
            stmt = stmt.where(Material.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, material: Material) -> Material:
        self._session.add(material)
        await self._session.flush()
        return material

    async def update(self, material: Material) -> Material:
        await self._session.flush()
        return material
