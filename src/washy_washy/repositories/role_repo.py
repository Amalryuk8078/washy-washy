"""Persistence for :class:`core.models.role.Role`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.role import Role


class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        return await self._session.get(Role, role_id)

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Role]:
        stmt = select(Role).where(Role.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, role: Role) -> Role:
        self._session.add(role)
        await self._session.flush()
        return role
